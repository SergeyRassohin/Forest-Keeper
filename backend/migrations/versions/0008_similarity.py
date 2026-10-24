"""Versioned pgvector retrieval artifacts. Never modifies historical business facts."""

from alembic import op

revision = "0008_similarity"
down_revision = "0007_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace
                     WHERE e.extname='vector' AND n.nspname='public') THEN
        RAISE EXCEPTION 'Required public pgvector extension unavailable';
      END IF;
    END $$;
    CREATE TABLE retrieval_versions (
      id uuid PRIMARY KEY, config jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE retrieval_state (
      id integer PRIMARY KEY CHECK(id=1), active_version_id uuid REFERENCES retrieval_versions);
    INSERT INTO retrieval_state(id) VALUES(1);
    CREATE TABLE decision_embeddings (
      id uuid PRIMARY KEY, decision_id uuid NOT NULL REFERENCES decisions,
      version_id uuid NOT NULL REFERENCES retrieval_versions,
      domain varchar(100) NOT NULL, entity_type varchar(100) NOT NULL,
      attribute_code varchar(64) NOT NULL, conflict_type varchar(32) NOT NULL,
      value_kind varchar(32) NOT NULL, unit varchar(32) NOT NULL,
      dimensions integer NOT NULL CHECK(dimensions=1024),
      embedding public.vector(1024) NOT NULL CHECK(public.vector_norm(embedding)>0),
      features jsonb NOT NULL, feature_hash varchar(64) NOT NULL, input_hash varchar(64) NOT NULL,
      vector_hash varchar(64) NOT NULL CHECK(vector_hash=
        encode(sha256(public.vector_send(embedding)),'hex')),
      created_at timestamptz NOT NULL DEFAULT now(), indexed_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(version_id,decision_id));
    CREATE INDEX ix_embedding_filters ON decision_embeddings
      (version_id,domain,entity_type,attribute_code,conflict_type,value_kind,unit);
    CREATE INDEX ix_embedding_integrity ON decision_embeddings(version_id,decision_id)
      WHERE vector_hash IS DISTINCT FROM encode(sha256(public.vector_send(embedding)),'hex')
      OR feature_hash IS DISTINCT FROM input_hash OR dimensions<>1024;
    CREATE TABLE retrieval_queries (
      version_id uuid NOT NULL REFERENCES retrieval_versions, context_hash varchar(64) NOT NULL,
      features jsonb NOT NULL, embedding public.vector(1024) NOT NULL
        CHECK(public.vector_norm(embedding)>0),
      vector_hash varchar(64) NOT NULL CHECK(vector_hash=
        encode(sha256(public.vector_send(embedding)),'hex')),
      created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(version_id,context_hash));
    CREATE TABLE retrieval_items (
      version_id uuid NOT NULL REFERENCES retrieval_versions,
      decision_id uuid NOT NULL REFERENCES decisions, reason varchar(64) NOT NULL,
      PRIMARY KEY(version_id,decision_id));
    CREATE TABLE retrieval_runs (
      id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES retrieval_versions,
      status varchar(16) NOT NULL
        CHECK(status IN ('NEW','QUEUED','PROCESSING','COMPLETED','FAILED')),
      processed integer NOT NULL DEFAULT 0, indexed integer NOT NULL DEFAULT 0,
      skipped integer NOT NULL DEFAULT 0, batch_size integer NOT NULL
        CHECK(batch_size BETWEEN 1 AND 500),
      last_decision_id uuid, activate boolean NOT NULL DEFAULT false, error_code varchar(64),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now());
    CREATE INDEX ix_retrieval_runs_version_id ON retrieval_runs(version_id);
    CREATE FUNCTION guard_retrieval_artifact() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Retrieval artifact is immutable; create a new version'; END $$;
    CREATE TRIGGER retrieval_version_immutable BEFORE UPDATE OR DELETE ON retrieval_versions
      FOR EACH ROW EXECUTE FUNCTION guard_retrieval_artifact();
    CREATE TRIGGER retrieval_vector_immutable BEFORE UPDATE OR DELETE ON decision_embeddings
      FOR EACH ROW EXECUTE FUNCTION guard_retrieval_artifact();
    CREATE TRIGGER retrieval_item_immutable BEFORE UPDATE OR DELETE ON retrieval_items
      FOR EACH ROW EXECUTE FUNCTION guard_retrieval_artifact();
    CREATE TRIGGER retrieval_query_immutable BEFORE UPDATE OR DELETE ON retrieval_queries
      FOR EACH ROW EXECUTE FUNCTION guard_retrieval_artifact();
    """)


def downgrade() -> None:
    op.execute("""
    DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM decision_embeddings) THEN
        RAISE EXCEPTION 'Preserve derived audit: downgrade with vectors is refused';
      END IF;
    END $$;
    DROP TABLE retrieval_runs, retrieval_items, retrieval_queries, decision_embeddings,
      retrieval_state, retrieval_versions;
    DROP FUNCTION guard_retrieval_artifact();
    """)
