"""Explainable matching over immutable normalization history; no physical merge."""

from alembic import op

revision = "0005_matching"
down_revision = "0004_normalization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE matching_runs (
        id UUID PRIMARY KEY, status VARCHAR(16) NOT NULL,
        input_analysis_ids JSONB NOT NULL, profile_id UUID NOT NULL,
        profile_hash VARCHAR(64) NOT NULL, profile_snapshot JSONB NOT NULL,
        input_context JSONB NOT NULL, actor_id UUID NOT NULL,
        records_processed INTEGER NOT NULL, candidates_generated INTEGER NOT NULL,
        status_counts JSONB NOT NULL, diagnostics JSONB NOT NULL, last_record_id UUID,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at TIMESTAMPTZ, error_text TEXT,
        CHECK(status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED'))
    )""")
    op.execute("CREATE INDEX ix_matching_created ON matching_runs(created_at,id)")
    op.execute("CREATE INDEX ix_matching_profile ON matching_runs(profile_hash)")
    op.execute("""CREATE TABLE match_candidates (
        id UUID PRIMARY KEY, raw_record_a_id UUID NOT NULL REFERENCES raw_records(id),
        raw_record_b_id UUID NOT NULL REFERENCES raw_records(id), confidence NUMERIC(9,6) NOT NULL,
        evidence JSONB NOT NULL, status VARCHAR(16) NOT NULL, confirmed_by UUID,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK(raw_record_a_id < raw_record_b_id), CHECK(confidence >= 0 AND confidence <= 1),
        CHECK(status IN ('POSSIBLE_MATCH','MATCHED','NOT_MATCHED'))
    )""")
    op.execute(
        "CREATE INDEX ix_match_candidates_raw_record_a_id ON match_candidates(raw_record_a_id)"
    )
    op.execute(
        "CREATE INDEX ix_match_candidates_raw_record_b_id ON match_candidates(raw_record_b_id)"
    )
    op.execute("""CREATE TABLE matching_pairs (
        run_id UUID NOT NULL REFERENCES matching_runs(id),
        candidate_id UUID NOT NULL REFERENCES match_candidates(id),
        left_record_id UUID NOT NULL REFERENCES raw_records(id),
        right_record_id UUID NOT NULL REFERENCES raw_records(id),
        PRIMARY KEY(run_id,candidate_id), CHECK(left_record_id <> right_record_id)
    )""")
    op.execute(
        "CREATE UNIQUE INDEX uq_matching_pair ON matching_pairs"
        "(run_id,left_record_id,right_record_id)"
    )
    op.execute("CREATE INDEX ix_matching_right ON matching_pairs(run_id,right_record_id)")
    op.execute("""CREATE FUNCTION protect_matching_origin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (NEW.input_analysis_ids,NEW.profile_id,NEW.profile_hash,NEW.profile_snapshot,
              NEW.input_context,NEW.actor_id,NEW.created_at) IS DISTINCT FROM
             (OLD.input_analysis_ids,OLD.profile_id,OLD.profile_hash,OLD.profile_snapshot,
              OLD.input_context,OLD.actor_id,OLD.created_at) THEN
            RAISE EXCEPTION 'Matching origin is immutable';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER matching_origin_immutable BEFORE UPDATE ON matching_runs "
        "FOR EACH ROW EXECUTE FUNCTION protect_matching_origin()"
    )
    op.execute(
        "CREATE TRIGGER matching_pairs_append_only BEFORE UPDATE OR DELETE "
        "ON matching_pairs FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()"
    )
    op.execute("""CREATE FUNCTION protect_match_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Match history is immutable'; END IF;
          IF (NEW.id,NEW.raw_record_a_id,NEW.raw_record_b_id,NEW.confidence,
              NEW.evidence,NEW.created_at)
              IS DISTINCT FROM
             (OLD.id,OLD.raw_record_a_id,OLD.raw_record_b_id,OLD.confidence,OLD.evidence,OLD.created_at)
             OR OLD.status <> 'POSSIBLE_MATCH' OR NEW.status NOT IN ('MATCHED','NOT_MATCHED') THEN
            RAISE EXCEPTION 'Forbidden match transition or history mutation';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER match_candidate_guard BEFORE UPDATE OR DELETE "
        "ON match_candidates FOR EACH ROW EXECUTE FUNCTION protect_match_candidate()"
    )


def downgrade() -> None:
    for table in ["matching_pairs", "match_candidates", "matching_runs"]:
        op.drop_table(table)
    op.execute("DROP FUNCTION protect_match_candidate()")
    op.execute("DROP FUNCTION protect_matching_origin()")
