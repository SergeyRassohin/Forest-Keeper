"""Source systems, import batches and immutable raw records.

DDL is a frozen schema snapshot: future model changes must not change this migration.
"""

from alembic import op

revision = "0003_imports"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE source_systems (
	id UUID NOT NULL,
	name VARCHAR(200) NOT NULL,
	code VARCHAR(64) NOT NULL,
	source_type VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	authority_scope JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (source_type IN ('FILE','ONE_C')),
	CHECK (status IN ('ACTIVE','DISABLED','ARCHIVED')),
	UNIQUE (code)
)""")
    op.execute("""CREATE TABLE import_batches (
	id UUID NOT NULL,
	source_system_id UUID NOT NULL,
	original_filename VARCHAR(255) NOT NULL,
	format VARCHAR(8) NOT NULL,
	file_hash VARCHAR(64) NOT NULL,
	storage_uri VARCHAR(80) NOT NULL,
	status VARCHAR(32) NOT NULL,
	uploaded_by UUID NOT NULL,
	uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	error_text TEXT,
	records_loaded INTEGER NOT NULL,
	records_failed INTEGER NOT NULL,
	retry_of_id UUID,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (format IN ('CSV','XLSX','XML')),
	CHECK (status IN ('NEW','QUEUED','PROCESSING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED')),
	FOREIGN KEY(source_system_id) REFERENCES source_systems (id),
	FOREIGN KEY(retry_of_id) REFERENCES import_batches (id)
)""")
    op.execute("CREATE INDEX ix_import_batches_retry_of_id ON import_batches (retry_of_id)")
    op.execute(
        "CREATE INDEX ix_import_batches_source_system_id ON import_batches (source_system_id)"
    )
    op.execute("CREATE INDEX ix_import_uploaded ON import_batches (uploaded_at, id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_import_original_checksum ON import_batches "
        "(source_system_id, file_hash) WHERE retry_of_id IS NULL"
    )
    op.execute("""CREATE TABLE raw_records (
	id UUID NOT NULL,
	import_batch_id UUID NOT NULL,
	source_record_key TEXT,
	source_object_type VARCHAR(200) NOT NULL,
	raw_payload JSONB NOT NULL,
	source_position JSONB NOT NULL,
	position_key VARCHAR(100) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (import_batch_id, position_key),
	FOREIGN KEY(import_batch_id) REFERENCES import_batches (id)
)""")
    op.execute("CREATE INDEX ix_raw_records_import_batch_id ON raw_records (import_batch_id)")
    op.execute("""CREATE TABLE import_errors (
	id UUID NOT NULL,
	import_batch_id UUID NOT NULL,
	source_position JSONB NOT NULL,
	position_key VARCHAR(100) NOT NULL,
	code VARCHAR(40) NOT NULL,
	message VARCHAR(300) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (import_batch_id, position_key, code),
	FOREIGN KEY(import_batch_id) REFERENCES import_batches (id)
)""")
    op.execute("CREATE INDEX ix_import_errors_import_batch_id ON import_errors (import_batch_id)")
    # Use the established append-only audit protection for historical raw facts too.
    op.execute("""
        CREATE TRIGGER raw_records_append_only BEFORE UPDATE OR DELETE ON raw_records
        FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()
    """)
    op.execute("""
        CREATE FUNCTION protect_import_origin() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (NEW.source_system_id, NEW.original_filename, NEW.format, NEW.file_hash,
              NEW.storage_uri, NEW.uploaded_by, NEW.uploaded_at, NEW.retry_of_id)
            IS DISTINCT FROM
             (OLD.source_system_id, OLD.original_filename, OLD.format, OLD.file_hash,
              OLD.storage_uri, OLD.uploaded_by, OLD.uploaded_at, OLD.retry_of_id) THEN
            RAISE EXCEPTION 'Import origin is immutable';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER import_origin_immutable BEFORE UPDATE ON import_batches
        FOR EACH ROW EXECUTE FUNCTION protect_import_origin()
    """)


def downgrade() -> None:
    op.drop_table("import_errors")
    op.drop_table("raw_records")
    op.drop_table("import_batches")
    op.execute("DROP FUNCTION protect_import_origin()")
    op.drop_table("source_systems")
