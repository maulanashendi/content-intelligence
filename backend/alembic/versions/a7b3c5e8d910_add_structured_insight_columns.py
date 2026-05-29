"""add structured insight columns to cluster_insight

Revision ID: a7b3c5e8d910
Revises: f3e2d1c0b9a8
Create Date: 2026-05-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b3c5e8d910"
down_revision: str = "f3e2d1c0b9a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cluster_insight",
        sa.Column("what_happened", sa.Text(), nullable=True),
    )
    op.add_column(
        "cluster_insight",
        sa.Column("parties_involved", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column(
        "cluster_insight",
        sa.Column("editorial_angle", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cluster_insight", "editorial_angle")
    op.drop_column("cluster_insight", "parties_involved")
    op.drop_column("cluster_insight", "what_happened")
