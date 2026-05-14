"""add article analysis columns and summary array

Revision ID: b0c7e295504b
Revises: 6920af718875
Create Date: 2026-05-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0c7e295504b"
down_revision: str = "6920af718875"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_cluster_member",
        sa.Column("main_entity", sa.Text(), nullable=True),
    )
    op.add_column(
        "article_cluster_member",
        sa.Column("information_claims", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    # summary was Text, always NULL (never surfaced to API). Cast via NULL — no
    # existing values to preserve.
    op.execute(
        "ALTER TABLE cluster_insight ALTER COLUMN summary TYPE text[] USING NULL::text[]"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE cluster_insight ALTER COLUMN summary TYPE text USING NULL"
    )
    op.drop_column("article_cluster_member", "information_claims")
    op.drop_column("article_cluster_member", "main_entity")
