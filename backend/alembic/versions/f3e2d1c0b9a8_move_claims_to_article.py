"""move main_entity and information_claims from article_cluster_member to article

Revision ID: f3e2d1c0b9a8
Revises: c3f1a8b29e70
Create Date: 2026-05-13 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3e2d1c0b9a8"
down_revision: str = "c3f1a8b29e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("article", sa.Column("main_entity", sa.Text(), nullable=True))
    op.add_column(
        "article",
        sa.Column("information_claims", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.drop_column("article_cluster_member", "information_claims")
    op.drop_column("article_cluster_member", "main_entity")


def downgrade() -> None:
    op.add_column(
        "article_cluster_member",
        sa.Column("main_entity", sa.Text(), nullable=True),
    )
    op.add_column(
        "article_cluster_member",
        sa.Column("information_claims", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.drop_column("article", "information_claims")
    op.drop_column("article", "main_entity")
