"""perf_hnsw_and_tsvector

Switch embedding index from IVFFlat to HNSW and add a stored tsvector generated
column with a GIN index for full-text search on the chunks table.

Revision ID: c9d4e5f6a7b8
Revises: b5e2a7c3f1d9
Create Date: 2026-03-23 00:00:00.000000

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c9d4e5f6a7b8'
down_revision = 'b5e2a7c3f1d9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add stored generated tsvector column for full-text search.
    op.execute(
        text(
            "ALTER TABLE chunks ADD COLUMN text_tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
        )
    )

    # 2. Add GIN index on the generated tsvector column.
    op.execute(
        text("CREATE INDEX ix_chunks_text_tsv ON chunks USING GIN (text_tsv)")
    )

    # 3. Leave the embedding ANN index to the dedicated maintenance job.
    # The application can operate without it, and building HNSW inline can
    # make deploys look hung on larger datasets.
    op.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding"))


def downgrade():
    # 1. Drop the embedding index if present.
    op.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding"))

    # 2. Drop the GIN full-text search index.
    op.execute(text("DROP INDEX IF EXISTS ix_chunks_text_tsv"))

    # 3. Drop the stored generated tsvector column.
    op.execute(text("ALTER TABLE chunks DROP COLUMN IF EXISTS text_tsv"))
