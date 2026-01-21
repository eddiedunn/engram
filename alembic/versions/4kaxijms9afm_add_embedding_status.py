"""add_embedding_status

Revision ID: 4kaxijms9afm
Revises:
Create Date: 2026-01-19 19:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4kaxijms9afm'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add embedding_status column to chunks table
    op.add_column(
        'chunks',
        sa.Column('embedding_status', sa.String(20), server_default='complete')
    )
    # Index for finding pending embeddings
    op.create_index(
        'ix_chunks_embedding_status',
        'chunks',
        ['embedding_status'],
        postgresql_where=sa.text("embedding_status = 'pending'")
    )


def downgrade():
    op.drop_index('ix_chunks_embedding_status', table_name='chunks')
    op.drop_column('chunks', 'embedding_status')
