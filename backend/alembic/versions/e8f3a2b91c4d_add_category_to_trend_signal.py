"""add_category_to_trend_signal

Revision ID: e8f3a2b91c4d
Revises: 5c201ef892c5
Create Date: 2026-05-04 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f3a2b91c4d"
down_revision: Union[str, None] = "5c201ef892c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trend_signal",
        sa.Column("category", sa.String(), server_default="all", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("trend_signal", "category")
