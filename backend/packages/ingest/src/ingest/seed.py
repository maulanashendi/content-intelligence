import logging

from core.db import get_session
from core.models import ContentSource, SourceStatus, SourceType
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

NEWS_SOURCES = [
    {
        "name": "ANTARA – Top News",
        "url": "https://www.antaranews.com/rss/top-news",
        "source_type": SourceType.rss,
    },
    {
        "name": "ANTARA – Ekonomi",
        "url": "https://www.antaranews.com/rss/ekonomi",
        "source_type": SourceType.rss,
    },
    {
        "name": "Coconuts – Jakarta",
        "url": "https://coconuts.co/jakarta/feed/",
        "source_type": SourceType.rss,
    },
    {
        "name": "Detik – Berita",
        "url": "https://news.detik.com/berita/rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "Detik – Finance",
        "url": "https://finance.detik.com/rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "Kompas",
        "url": "https://rss.kompas.com/api/feed/social?apikey=bc58c81819dff4b8d5c53540a2fc7ffd83e6314a",
        "source_type": SourceType.rss,
    },
    {
        "name": "Kontan – Keuangan",
        "url": "https://rss.kontan.co.id/news/keuangan",
        "source_type": SourceType.rss,
    },
    {
        "name": "Kontan – Nasional",
        "url": "https://rss.kontan.co.id/news/nasional",
        "source_type": SourceType.rss,
    },
    {
        "name": "Suara – Sitemap News",
        "url": "https://www.suara.com/sitemap_news.xml",
        "source_type": SourceType.rss,
    },
    {
        "name": "Liputan 6",
        "url": "https://feed.liputan6.com/rss/news",
        "source_type": SourceType.rss,
    },
    {
        "name": "Tempo – Nasional",
        "url": "https://rss.tempo.co/nasional",
        "source_type": SourceType.internal,
    },
    {
        "name": "Tempo – Bisnis",
        "url": "https://rss.tempo.co/bisnis",
        "source_type": SourceType.internal,
    },
    {
        "name": "CNN Indonesia – Ekonomi",
        "url": "https://www.cnnindonesia.com/ekonomi/rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "CNN Indonesia – Nasional",
        "url": "https://www.cnnindonesia.com/nasional/rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "CNBC Indonesia – News",
        "url": "https://www.cnbcindonesia.com/news/rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "CNBC Indonesia – Market",
        "url": "https://www.cnbcindonesia.com/market/rss/",
        "source_type": SourceType.rss,
    },
    {
        "name": "Republika Online – Nasional",
        "url": "https://www.republika.co.id/rss/nasional/",
        "source_type": SourceType.rss,
    },
    {
        "name": "Republika Online – Ekonomi",
        "url": "https://www.republika.co.id/rss/ekonomi/",
        "source_type": SourceType.rss,
    },
    {
        "name": "Media Indonesia",
        "url": "https://mediaindonesia.com/feed",
        "source_type": SourceType.rss,
    },
    {
        "name": "Tirto",
        "url": "https://tirto.id/sitemap/r/google-discover",
        "source_type": SourceType.rss,
    },
    {"name": "Tribunnews", "url": "https://www.tribunnews.com/rss", "source_type": SourceType.rss},
    {"name": "Merdeka", "url": "https://www.merdeka.com/feed/", "source_type": SourceType.rss},
    {"name": "VIVA", "url": "https://www.viva.co.id/get/all", "source_type": SourceType.rss},
    {"name": "SINDOnews", "url": "https://www.sindonews.com/feed", "source_type": SourceType.rss},
    {
        "name": "JPNN",
        "url": "https://www.jpnn.com/index.php?mib=rss",
        "source_type": SourceType.rss,
    },
    {
        "name": "Okezone – Breaking News",
        "url": "https://sindikasi.okezone.com/index.php/rss/0/RSS2.0",
        "source_type": SourceType.rss,
    },
    {
        "name": "Okezone – News",
        "url": "https://sindikasi.okezone.com/index.php/rss/1/RSS2.0",
        "source_type": SourceType.rss,
    },
    {
        "name": "Okezone – Economy",
        "url": "https://sindikasi.okezone.com/index.php/rss/11/RSS2.0",
        "source_type": SourceType.rss,
    },
    {
        "name": "VOA Indonesia – Berita",
        "url": "https://www.voaindonesia.com/api/zmgqol",
        "source_type": SourceType.rss,
    },
    {
        "name": "VOA Indonesia – Ekonomi",
        "url": "https://www.voaindonesia.com/api/zvgqml",
        "source_type": SourceType.rss,
    },
    {
        "name": "VOA Indonesia – Politik",
        "url": "https://www.voaindonesia.com/api/z_gqil",
        "source_type": SourceType.rss,
    },
    {"name": "Fajar", "url": "https://fajar.co.id/feed/", "source_type": SourceType.rss},
    {"name": "Waspada Online", "url": "https://waspada.co.id/feed/", "source_type": SourceType.rss},
    {
        "name": "The Bali Times",
        "url": "https://thebalitimes.com/feed/",
        "source_type": SourceType.rss,
    },
    {"name": "Online24jam", "url": "https://online24jam.com/feed/", "source_type": SourceType.rss},
]


async def seed_sources() -> int:
    async with get_session() as session:
        inserted = 0
        for feed in NEWS_SOURCES:
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

    total = len(NEWS_SOURCES)
    logger.info("seed complete", extra={"total": total, "inserted": inserted})
    return inserted
