"""add rss trends gsc signals to cluster_insight

Revision ID: c9d5e7f1a2b3
Revises: a7b3c5e8d910
Create Date: 2026-05-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision: str = "c9d5e7f1a2b3"
down_revision: str = "a7b3c5e8d910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cluster_insight",
        sa.Column("weighted_trend_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "cluster_insight",
        sa.Column(
            "tempo_gsc_impressions",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "cluster_insight",
        sa.Column(
            "gsc_demand_gap",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "cluster_insight",
        sa.Column("competitor_freshness_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cluster_insight", "competitor_freshness_days")
    op.drop_column("cluster_insight", "gsc_demand_gap")
    op.drop_column("cluster_insight", "tempo_gsc_impressions")
    op.drop_column("cluster_insight", "weighted_trend_score")
