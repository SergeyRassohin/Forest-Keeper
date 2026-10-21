"""Immutable conflict evidence and checkpointed deterministic analysis."""

from alembic import op

revision = "0006_conflicts"
down_revision = "0005_matching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE conflict_runs (
                id UUID NOT NULL,
                matching_run_id UUID NOT NULL,
                status VARCHAR(16) NOT NULL,
                profile_hash VARCHAR(64) NOT NULL,
                profile_snapshot JSONB NOT NULL,
                actor_id UUID NOT NULL,
                records_processed INTEGER NOT NULL,
                attributes_evaluated INTEGER NOT NULL,
                conflicts_generated INTEGER NOT NULL,
                status_counts JSONB NOT NULL,
                last_candidate_id UUID,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                completed_at TIMESTAMP WITH TIME ZONE,
                error_text TEXT,
                PRIMARY KEY (id),
                CHECK (status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED')),
                FOREIGN KEY(matching_run_id) REFERENCES matching_runs (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_conflict_runs_created ON conflict_runs (created_at, id)
    """)
    op.execute("""
        CREATE INDEX ix_conflict_runs_matching_run_id ON conflict_runs (matching_run_id)
    """)
    op.execute("""
        CREATE TABLE conflicts (
                id UUID NOT NULL,
                entity_id UUID NOT NULL,
                analysis_run_id UUID NOT NULL,
                matching_run_id UUID NOT NULL,
                match_candidate_id UUID NOT NULL,
                attribute_code VARCHAR(64) NOT NULL,
                conflict_type VARCHAR(32) NOT NULL,
                severity VARCHAR(16) NOT NULL,
                status VARCHAR(32) NOT NULL,
                values_snapshot JSONB NOT NULL,
                basis JSONB NOT NULL,
                detected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                PRIMARY KEY (id),
                CHECK (conflict_type IN
        ('VALUE_MISMATCH','MISSING','DUPLICATE','RULE_VIOLATION','ANOMALY')),
                CHECK (status IN ('OPEN','IN_REVIEW','RESOLVED','INSUFFICIENT_DATA')),
                CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
                FOREIGN KEY(entity_id) REFERENCES canonical_entities (id),
                FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id),
                FOREIGN KEY(matching_run_id) REFERENCES matching_runs (id),
                FOREIGN KEY(match_candidate_id) REFERENCES match_candidates (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_conflicts_created ON conflicts (detected_at, id)
    """)
    op.execute("""
        CREATE INDEX ix_conflicts_entity_id ON conflicts (entity_id)
    """)
    op.execute("""
        CREATE INDEX ix_conflicts_filter ON conflicts (conflict_type, status, severity)
    """)
    op.execute("""
        CREATE INDEX ix_conflicts_match_candidate_id ON conflicts (match_candidate_id)
    """)
    op.execute("""
        CREATE INDEX ix_conflicts_matching_run_id ON conflicts (matching_run_id)
    """)
    op.execute("""
        CREATE TABLE conflict_inputs (
                run_id UUID NOT NULL,
                candidate_id UUID NOT NULL,
                PRIMARY KEY (run_id, candidate_id),
                FOREIGN KEY(run_id) REFERENCES conflict_runs (id),
                FOREIGN KEY(candidate_id) REFERENCES match_candidates (id)
        )
    """)
    op.execute("""
        CREATE TABLE conflict_outputs (
                run_id UUID NOT NULL,
                conflict_id UUID NOT NULL,
                PRIMARY KEY (run_id, conflict_id),
                FOREIGN KEY(run_id) REFERENCES conflict_runs (id),
                FOREIGN KEY(conflict_id) REFERENCES conflicts (id)
        )
    """)
    op.execute("CREATE INDEX ix_conflicts_run_created ON conflicts(matching_run_id,detected_at,id)")
    op.execute("""
        CREATE TRIGGER conflicts_append_only BEFORE UPDATE OR DELETE ON conflicts FOR EACH ROW
        EXECUTE FUNCTION reject_audit_mutation()
    """)
    op.execute("""
        CREATE TRIGGER conflict_inputs_append_only BEFORE UPDATE OR DELETE ON conflict_inputs
        FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()
    """)
    op.execute("""
        CREATE TRIGGER conflict_outputs_append_only BEFORE UPDATE OR DELETE ON conflict_outputs
        FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()
    """)
    op.execute("""
        CREATE FUNCTION protect_conflict_origin() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
         IF
        (NEW.id,NEW.matching_run_id,NEW.profile_hash,NEW.profile_snapshot,NEW.actor_id,NEW.created_at)
        IS DISTINCT FROM
        (OLD.id,OLD.matching_run_id,OLD.profile_hash,OLD.profile_snapshot,OLD.actor_id,OLD.created_at)
        THEN RAISE EXCEPTION 'Conflict origin is immutable'; END IF; RETURN NEW; END $$
    """)
    op.execute("""
        CREATE TRIGGER conflict_origin_immutable BEFORE UPDATE ON conflict_runs FOR EACH ROW
        EXECUTE FUNCTION protect_conflict_origin()
    """)


def downgrade() -> None:
    for table in ["conflict_outputs", "conflict_inputs", "conflicts", "conflict_runs"]:
        op.drop_table(table)
    op.execute("""
        DROP FUNCTION protect_conflict_origin()
    """)
