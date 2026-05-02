import logging

from core.db import get_session
from core.models import ContentSource, SourceStatus, SourceType
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

ECONOMY_RSS_FEEDS = [
    {
        "name": "Detik Finance",
        "url": "https://rss.detik.com/index.php/finance",
        "source_type": SourceType.rss,
    },
    {
        "name": "Kompas Ekonomi",
        "url": "https://rss.kompas.com/ekonomi",
        "source_type": SourceType.rss,
    },
    {
        "name": "Tirto Ekonomi",
        "url": "https://tirto.id/rss/ekonomi",
        "source_type": SourceType.rss,
    },
    {
        "name": "CNN Indonesia Ekonomi",
        "url": "https://www.cnnindonesia.com/ekonomi/rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "Kontan Ekonomi",
        "url": "https://www.kontan.co.id/rss/ekonomi.xml",
        "source_type": SourceType.rss,
    },
]


async def seed_sources() -> int:
    async with get_session() as session:
        inserted = 0
        for feed in ECONOMY_RSS_FEEDS:
            stmt = pg_insert(ContentSource).values(
                name=feed["name"],
                url=feed["url"],
                source_type=feed["source_type"],
                is_enabled=True,
                status=SourceStatus.active,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
            result = await session.execute(stmt)
            if result.rowcount and result.rowcount > 0:
                inserted += 1
                logger.info(
                    "seeded source", extra={"source_name": feed["name"], "url": feed["url"]}
                )
            else:
                logger.info(
                    "source already exists", extra={"source_name": feed["name"], "url": feed["url"]}
                )

        await session.commit()

    total = len(ECONOMY_RSS_FEEDS)
    logger.info("seed complete", extra={"total": total, "inserted": inserted})
    return inserted
