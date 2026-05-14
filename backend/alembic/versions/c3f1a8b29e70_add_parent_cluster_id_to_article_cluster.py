"""add parent_cluster_id to article_cluster

Revision ID: c3f1a8b29e70
Revises: b0c7e295504b
Create Date: 2026-05-13 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f1a8b29e70"
down_revision: str = "b0c7e295504b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_cluster",
        sa.Column("parent_cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_article_cluster_parent_cluster_id",
        "article_cluster",
        "article_cluster",
        ["parent_cluster_id"],
        ["id"],
    )
    op.create_index(
        "ix_article_cluster_parent_cluster_id",
        "article_cluster",
        ["parent_cluster_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_article_cluster_parent_cluster_id", table_name="article_cluster")
    op.drop_constraint(
        "fk_article_cluster_parent_cluster_id", "article_cluster", type_="foreignkey"
    )
    op.drop_column("article_cluster", "parent_cluster_id")
