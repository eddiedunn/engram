"""fix_content_type_enum_lowercase

Convert content_type_enum to use lowercase values (youtube, article, etc.)
instead of uppercase. Normalizes existing data to lowercase as well.

This migration captures the manual fix applied to the production database.
It is written to be idempotent: if the enum already has lowercase values
(i.e. the DB was already fixed manually), running this migration is a no-op.

Revision ID: a3f8c2d1e9b7
Revises: 4kaxijms9afm
Create Date: 2026-03-05 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a3f8c2d1e9b7'
down_revision = '4kaxijms9afm'
branch_labels = None
depends_on = None


LOWERCASE_VALUES = ('youtube', 'article', 'podcast', 'document', 'note', 'other')
LOWERCASE_VALUES_WITH_MEETING = (
    'youtube',
    'article',
    'podcast',
    'meeting',
    'document',
    'note',
    'other',
)
UPPERCASE_VALUES = ('YOUTUBE', 'ARTICLE', 'PODCAST', 'DOCUMENT', 'NOTE', 'OTHER')


def upgrade():
    conn = op.get_bind()

    # Check if the enum already has lowercase values (was already fixed manually)
    result = conn.execute(
        text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'content_type_enum' "
            "ORDER BY enumsortorder"
        )
    ).fetchall()

    existing_values = [row[0] for row in result]

    if existing_values in (
        list(LOWERCASE_VALUES),
        list(LOWERCASE_VALUES_WITH_MEETING),
    ):
        # DB is already in the correct state — migration is a no-op
        return

    # Step 1: Convert content_type column to VARCHAR to detach from enum type
    op.execute(
        "ALTER TABLE content ALTER COLUMN content_type TYPE VARCHAR(50) "
        "USING content_type::text"
    )

    # Step 2: Drop the old enum type (uppercase values)
    op.execute("DROP TYPE IF EXISTS content_type_enum")

    # Step 3: Normalize existing data to canonical lowercase values.
    # Older pre-Alembic databases may contain ad-hoc values; map those to
    # 'other' so the enum cast stays forward-compatible.
    op.execute(
        """
        UPDATE content
        SET content_type = CASE LOWER(content_type)
            WHEN 'youtube' THEN 'youtube'
            WHEN 'article' THEN 'article'
            WHEN 'podcast' THEN 'podcast'
            WHEN 'meeting' THEN 'meeting'
            WHEN 'document' THEN 'document'
            WHEN 'note' THEN 'note'
            WHEN 'other' THEN 'other'
            ELSE 'other'
        END
        """
    )

    # Step 4: Create new enum type with lowercase values
    op.execute(
        "CREATE TYPE content_type_enum AS ENUM "
        "('youtube', 'article', 'podcast', 'meeting', 'document', 'note', 'other')"
    )

    # Step 5: Convert column back to the new enum type
    op.execute(
        "ALTER TABLE content ALTER COLUMN content_type TYPE content_type_enum "
        "USING content_type::content_type_enum"
    )


def downgrade():
    conn = op.get_bind()

    # Check if the enum already has uppercase values (already downgraded)
    result = conn.execute(
        text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'content_type_enum' "
            "ORDER BY enumsortorder"
        )
    ).fetchall()

    existing_values = [row[0] for row in result]

    if existing_values == list(UPPERCASE_VALUES):
        # Already downgraded — no-op
        return

    # Step 1: Convert content_type column to VARCHAR
    op.execute(
        "ALTER TABLE content ALTER COLUMN content_type TYPE VARCHAR(50) "
        "USING content_type::text"
    )

    # Step 2: Drop the lowercase enum type
    op.execute("DROP TYPE IF EXISTS content_type_enum")

    # Step 3: Normalize existing data to uppercase
    op.execute("UPDATE content SET content_type = UPPER(content_type)")

    # Step 4: Recreate enum type with uppercase values
    op.execute(
        "CREATE TYPE content_type_enum AS ENUM "
        "('YOUTUBE', 'ARTICLE', 'PODCAST', 'DOCUMENT', 'NOTE', 'OTHER')"
    )

    # Step 5: Convert column back to the old enum type
    op.execute(
        "ALTER TABLE content ALTER COLUMN content_type TYPE content_type_enum "
        "USING content_type::content_type_enum"
    )
