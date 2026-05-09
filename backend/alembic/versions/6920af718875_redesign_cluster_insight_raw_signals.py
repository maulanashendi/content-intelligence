"""redesign cluster_insight raw signals

Revision ID: 6920af718875
Revises: 1104b4ad5d15
Create Date: 2026-05-09 11:16:47.757953

"""

import sqlalchemy as sa
from alembic import op

revision: str = "6920af718875"
down_revision: str = "1104b4ad5d15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # D24 disabled scoring; existing rows are stale and would mix with the new
    # shape. Wipe before altering columns. The next post-deploy scoring run
    # repopulates everything from current cluster state.
    op.execute("DELETE FROM cluster_insight")

    # Drop composite-era columns and the enum type they used.
    op.drop_column("cluster_insight", "novelty_score")
    op.drop_column("cluster_insight", "coverage_score")
    op.drop_column("cluster_insight", "recommendation")
    op.execute("DROP TYPE IF EXISTS insightrecommendation")

    # Add raw-signal columns. Non-nullable columns get server_default so the
    # earlier DELETE+ADD COLUMN sequence is safe even though there are no rows.
    op.add_column(
        "cluster_insight",
        sa.Column("competitor_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "cluster_insight",
        sa.Column("trend_match_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "cluster_insight",
        sa.Column(
            "tempo_covered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "cluster_insight",
        sa.Column("last_internal_days_ago", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cluster_insight",
        sa.Column(
            "underperformed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("cluster_insight", "underperformed")
    op.drop_column("cluster_insight", "last_internal_days_ago")
    op.drop_column("cluster_insight", "tempo_covered")
    op.drop_column("cluster_insight", "trend_match_count")
    op.drop_column("cluster_insight", "competitor_count")

    insight_recommendation = sa.Enum(
        "trending", "worth_writing", "saturated", name="insightrecommendation"
    )
    insight_recommendation.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "cluster_insight",
        sa.Column("recommendation", insight_recommendation, nullable=True),
    )
    op.add_column("cluster_insight", sa.Column("coverage_score", sa.Float(), nullable=True))
    op.add_column("cluster_insight", sa.Column("novelty_score", sa.Float(), nullable=True))
