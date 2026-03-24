"""add_meeting_content_type

Add 'meeting' to the content_type_enum PostgreSQL enum type.

Revision ID: b5e2a7c3f1d9
Revises: a3f8c2d1e9b7
Create Date: 2026-03-22 12:00:00.000000

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b5e2a7c3f1d9'
down_revision = 'a3f8c2d1e9b7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Check if 'meeting' already exists in the enum
    result = conn.execute(
        text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'content_type_enum' "
            "ORDER BY enumsortorder"
        )
    ).fetchall()

    existing_values = [row[0] for row in result]

    if 'meeting' in existing_values:
        # Already present — no-op
        return

    # Add 'meeting' to the enum type.
    # BEFORE is used to place it after 'podcast' and before 'document'.
    op.execute(
        "ALTER TYPE content_type_enum ADD VALUE 'meeting' BEFORE 'document'"
    )


def downgrade():
    # PostgreSQL does not support removing values from an enum type directly.
    # To fully downgrade, we would need to recreate the enum without 'meeting'.
    # This is left as a manual step since ALTER TYPE ... DROP VALUE is not supported.
    conn = op.get_bind()

    # Step 1: Convert column to VARCHAR
    op.execute(
        "ALTER TABLE content ALTER COLUMN content_type TYPE VARCHAR(50) "
        "USING content_type::text"
    )

    # Step 2: Drop the enum type
    op.execute("DROP TYPE IF EXISTS content_type_enum")

    # Step 3: Update any 'meeting' rows to 'other'
    op.execute("UPDATE content SET content_type = 'other' WHERE content_type = 'meeting'")

    # Step 4: Recreate enum without 'meeting'
    op.execute(
        "CREATE TYPE content_type_enum AS ENUM "
        "('youtube', 'article', 'podcast', 'document', 'note', 'other')"
    )

    # Step 5: Convert column back to enum
    op.execute(
        "ALTER TABLE content ALTER COLUMN content_type TYPE content_type_enum "
        "USING content_type::content_type_enum"
    )
