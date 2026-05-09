"""backfill trends scrape_status

Revision ID: 1104b4ad5d15
Revises: d5057fd81f8b
Create Date: 2026-05-09 11:04:14.415422

"""

from alembic import op

revision: str = "1104b4ad5d15"
down_revision: str = "d5057fd81f8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trend-scoped backfill: only articles linked via trend_signal_article whose
    # scrape_status is NULL and which still have no body. Per D25 we do not
    # backfill all NULL-status articles; this targets the specific bug from
    # the trends ingest path.
    op.execute(
        """
        UPDATE article
        SET scrape_status = 'pending'
        WHERE scrape_status IS NULL
          AND content IS NULL
          AND id IN (
            SELECT DISTINCT article_id FROM trend_signal_article
          )
        """
    )


def downgrade() -> None:
    # No reliable inverse: we cannot tell which rows we set vs which were
    # already 'pending'. Leaving the data in place is safe.
    pass
