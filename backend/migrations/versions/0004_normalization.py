"""Versioned pre-match normalization; no matching or destructive raw backfill."""

from alembic import op

revision = "0004_normalization"
down_revision = "0003_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_raw_import_id ON raw_records(import_batch_id,id)")
    op.execute("""CREATE TABLE analysis_runs (
        id UUID PRIMARY KEY, status VARCHAR(16) NOT NULL,
        import_batch_ids JSONB NOT NULL, template_id UUID NOT NULL,
        mapping_hash VARCHAR(64) NOT NULL, mapping_snapshot JSONB NOT NULL,
        actor_id UUID NOT NULL, records_processed INTEGER NOT NULL,
        values_processed INTEGER NOT NULL, quality_counts JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), error_text TEXT,
        CHECK(status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED'))
    )""")
    op.execute("CREATE INDEX ix_analysis_created ON analysis_runs(created_at,id)")
    op.execute("""CREATE TABLE canonical_entities (
        id UUID PRIMARY KEY, domain VARCHAR(100) NOT NULL,
        entity_type VARCHAR(100) NOT NULL, display_name VARCHAR(200) NOT NULL,
        status VARCHAR(32), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), CHECK(status IS NULL)
    )""")
    op.execute("""CREATE TABLE entity_values (
        id UUID PRIMARY KEY, entity_id UUID NOT NULL REFERENCES canonical_entities(id),
        attribute_code VARCHAR(64) NOT NULL, raw_record_id UUID NOT NULL REFERENCES raw_records(id),
        raw_value JSONB NOT NULL, normalized_value JSONB NOT NULL, unit VARCHAR(32),
        quality_status VARCHAR(16) NOT NULL, normalization_rule JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK(quality_status IN ('VALID','WARNING','INVALID','UNKNOWN'))
    )""")
    op.execute("CREATE UNIQUE INDEX uq_entity_attribute ON entity_values(entity_id,attribute_code)")
    op.execute("CREATE INDEX ix_entity_values_entity_id ON entity_values(entity_id)")
    op.execute("CREATE INDEX ix_entity_values_raw_record_id ON entity_values(raw_record_id)")
    op.execute("""CREATE TABLE analysis_records (
        analysis_id UUID NOT NULL REFERENCES analysis_runs(id),
        raw_record_id UUID NOT NULL REFERENCES raw_records(id),
        entity_id UUID REFERENCES canonical_entities(id), details JSONB NOT NULL,
        PRIMARY KEY(analysis_id,raw_record_id)
    )""")
    for table in ["canonical_entities", "entity_values", "analysis_records"]:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()"
        )
    op.execute("""CREATE FUNCTION protect_analysis_origin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (NEW.import_batch_ids,NEW.template_id,NEW.mapping_hash,NEW.mapping_snapshot,
              NEW.actor_id,NEW.created_at) IS DISTINCT FROM
             (OLD.import_batch_ids,OLD.template_id,OLD.mapping_hash,OLD.mapping_snapshot,
              OLD.actor_id,OLD.created_at) THEN
            RAISE EXCEPTION 'Analysis origin is immutable';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute(
        "CREATE TRIGGER analysis_origin_immutable BEFORE UPDATE ON analysis_runs "
        "FOR EACH ROW EXECUTE FUNCTION protect_analysis_origin()"
    )


def downgrade() -> None:
    for table in ["analysis_records", "entity_values", "canonical_entities", "analysis_runs"]:
        op.drop_table(table)
    op.execute("DROP FUNCTION protect_analysis_origin()")
    op.drop_index("ix_raw_import_id", table_name="raw_records")
