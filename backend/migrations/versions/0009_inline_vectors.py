"""Keep fixed-size vectors inline without changing immutable artifact values.

This transactional physical rewrite takes ACCESS EXCLUSIVE and needs transient
heap/index/WAL space. Run during coordinated maintenance, before API/workers resume.
The float4-array round trip preserves vector_send bytes; no UPDATE, trigger bypass,
model call, version activation or business-table write is performed.
"""

from alembic import op

revision = "0009_inline_vectors"
down_revision = "0008_similarity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep TYPE and STORAGE in the same ALTER: TYPE otherwise resets attstorage
    # to the type default before the physical rewrite starts.
    op.execute("""
        ALTER TABLE decision_embeddings
        ALTER COLUMN embedding TYPE public.vector(1024)
            USING (embedding::real[]::public.vector(1024)),
        ALTER COLUMN embedding SET STORAGE PLAIN
    """)
    op.execute("ANALYZE decision_embeddings")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE decision_embeddings
        ALTER COLUMN embedding TYPE public.vector(1024)
            USING (embedding::real[]::public.vector(1024)),
        ALTER COLUMN embedding SET STORAGE EXTERNAL
    """)
    op.execute("ANALYZE decision_embeddings")
