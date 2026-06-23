import logging

from core.db import get_session
from core.models import ContentSource, SourceStatus, SourceType
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

NEWS_SOURCES = [
    # --- Competitor RSS sources ---
    {"name": "ANTARA – Top News", "url": "https://www.antaranews.com/rss/top-news", "source_type": SourceType.rss},
    {"name": "ANTARA – Ekonomi", "url": "https://www.antaranews.com/rss/ekonomi", "source_type": SourceType.rss},
    {"name": "ANTARA – Terkini", "url": "https://www.antaranews.com/rss/terkini.xml", "source_type": SourceType.rss},
    {"name": "Bisnis.com", "url": "https://rss.bisnis.com/", "source_type": SourceType.rss},
    {"name": "CNA Indonesia", "url": "https://www.cna.id/api/v1/rss-outbound-feed?_format=xml", "source_type": SourceType.rss},
    {"name": "CNBC Indonesia – Market", "url": "https://www.cnbcindonesia.com/market/rss/", "source_type": SourceType.rss},
    {"name": "CNBC Indonesia – News", "url": "https://www.cnbcindonesia.com/news/rss", "source_type": SourceType.rss},
    {"name": "CNN Indonesia – Ekonomi", "url": "https://www.cnnindonesia.com/ekonomi/rss", "source_type": SourceType.rss},
    {"name": "CNN Indonesia – Nasional", "url": "https://www.cnnindonesia.com/nasional/rss", "source_type": SourceType.rss},
    {"name": "Coconuts – Jakarta", "url": "http://coconuts.co/jakarta/feed/", "source_type": SourceType.rss},
    {"name": "Detik – Berita", "url": "https://news.detik.com/berita/rss", "source_type": SourceType.rss},
    {"name": "Detik – Finance", "url": "https://finance.detik.com/rss", "source_type": SourceType.rss},
    {"name": "Detik – Health", "url": "https://health.detik.com/rss", "source_type": SourceType.rss},
    {"name": "Detik – Hot", "url": "https://hot.detik.com/rss", "source_type": SourceType.rss},
    {"name": "Detik – Inet", "url": "https://inet.detik.com/rss", "source_type": SourceType.rss},
    {"name": "Detik – Sport", "url": "https://sport.detik.com/rss", "source_type": SourceType.rss},
    {"name": "Google Trends – Indonesia", "url": "https://trends.google.com/trending/rss?geo=ID", "source_type": SourceType.rss},
    {"name": "JawaPos – Ekonomi", "url": "https://www.jawapos.com/ekonomi/rss", "source_type": SourceType.rss},
    {"name": "JawaPos – Nasional", "url": "https://www.jawapos.com/nasional/rss", "source_type": SourceType.rss},
    {"name": "JPNN", "url": "https://www.jpnn.com/index.php?mib=rss", "source_type": SourceType.rss},
    {"name": "Katadata", "url": "https://katadata.co.id/rss", "source_type": SourceType.rss},
    {"name": "Kompas", "url": "https://rss.kompas.com/api/feed/social?apikey=bc58c81819dff4b8d5c53540a2fc7ffd83e6314a", "source_type": SourceType.rss},
    {"name": "Kontan – Keuangan", "url": "https://rss.kontan.co.id/news/keuangan", "source_type": SourceType.rss},
    {"name": "Kontan – Nasional", "url": "https://rss.kontan.co.id/news/nasional", "source_type": SourceType.rss},
    {"name": "Kumparan", "url": "https://lapi.kumparan.com/v2.0/rss/", "source_type": SourceType.rss},
    {"name": "Liputan 6", "url": "https://feed.liputan6.com/rss/news", "source_type": SourceType.rss},
    {"name": "Media Indonesia", "url": "https://mediaindonesia.com/feed", "source_type": SourceType.rss},
    {"name": "Merdeka.com", "url": "https://www.merdeka.com/feed/", "source_type": SourceType.rss},
    {"name": "Republika Online – Ekonomi", "url": "https://www.republika.co.id/rss/ekonomi/", "source_type": SourceType.rss},
    {"name": "Republika Online – Nasional", "url": "https://www.republika.co.id/rss/nasional/", "source_type": SourceType.rss},
    {"name": "SINDOnews", "url": "https://www.sindonews.com/feed", "source_type": SourceType.rss},
    {"name": "Suara – Bisnis", "url": "https://www.suara.com/rss/bisnis", "source_type": SourceType.rss},
    {"name": "Suara – News", "url": "https://www.suara.com/rss/news", "source_type": SourceType.rss},
    {"name": "The Jakarta Post", "url": "https://rss.thejakartapost.com/home", "source_type": SourceType.rss},
    {"name": "Tirto", "url": "https://tirto.id/rss", "source_type": SourceType.rss},
    {"name": "Tribunnews", "url": "https://www.tribunnews.com/rss", "source_type": SourceType.rss},
    {"name": "VIVA.co.id", "url": "https://www.viva.co.id/get/all", "source_type": SourceType.rss},
    # --- Tempo internal sources (source_type=internal so scoring detects tempo_covered) ---
    {"name": "Tempo Free", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/", "source_type": SourceType.internal},
    {"name": "Tempo+", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/", "source_type": SourceType.internal},
    {"name": "Tempo – Digital", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/digital", "source_type": SourceType.internal},
    {"name": "Tempo+ – Digital", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/digital", "source_type": SourceType.internal},
    {"name": "Tempo – Ekonomi", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/ekonomi", "source_type": SourceType.internal},
    {"name": "Tempo+ – Ekonomi", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/ekonomi", "source_type": SourceType.internal},
    {"name": "Tempo – Gaya Hidup", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/gaya-hidup", "source_type": SourceType.internal},
    {"name": "Tempo+ – Gaya Hidup", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/gaya-hidup", "source_type": SourceType.internal},
    {"name": "Tempo – Hiburan", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/hiburan", "source_type": SourceType.internal},
    {"name": "Tempo+ – Hiburan", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/hiburan", "source_type": SourceType.internal},
    {"name": "Tempo – Hukum", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/hukum", "source_type": SourceType.internal},
    {"name": "Tempo+ – Hukum", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/hukum", "source_type": SourceType.internal},
    {"name": "Tempo – Internasional", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/internasional", "source_type": SourceType.internal},
    {"name": "Tempo+ – Internasional", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/internasional", "source_type": SourceType.internal},
    {"name": "Tempo – Investigasi", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/investigasi", "source_type": SourceType.internal},
    {"name": "Tempo+ – Investigasi", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/investigasi", "source_type": SourceType.internal},
    {"name": "Tempo – Lingkungan", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/lingkungan", "source_type": SourceType.internal},
    {"name": "Tempo+ – Lingkungan", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/lingkungan", "source_type": SourceType.internal},
    {"name": "Tempo – Olahraga", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/olahraga", "source_type": SourceType.internal},
    {"name": "Tempo+ – Olahraga", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/olahraga", "source_type": SourceType.internal},
    {"name": "Tempo – Otomotif", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/otomotif", "source_type": SourceType.internal},
    {"name": "Tempo+ – Otomotif", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/otomotif", "source_type": SourceType.internal},
    {"name": "Tempo – Politik", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/politik", "source_type": SourceType.internal},
    {"name": "Tempo+ – Politik", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/politik", "source_type": SourceType.internal},
    {"name": "Tempo – Prelude", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/prelude", "source_type": SourceType.internal},
    {"name": "Tempo+ – Prelude", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/prelude", "source_type": SourceType.internal},
    {"name": "Tempo – Sains", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/sains", "source_type": SourceType.internal},
    {"name": "Tempo+ – Sains", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/sains", "source_type": SourceType.internal},
    {"name": "Tempo – Sepakbola", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/sepakbola", "source_type": SourceType.internal},
    {"name": "Tempo+ – Sepakbola", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/sepakbola", "source_type": SourceType.internal},
    {"name": "Tempo – Teroka", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/teroka", "source_type": SourceType.internal},
    {"name": "Tempo+ – Teroka", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/teroka", "source_type": SourceType.internal},
    {"name": "Tempo – Tokoh", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/tokoh", "source_type": SourceType.internal},
    {"name": "Tempo+ – Tokoh", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/tokoh", "source_type": SourceType.internal},
    {"name": "Tempo – Wawancara", "url": "https://pustaka-api.tempo.co/single-brand/rss/free/wawancara", "source_type": SourceType.internal},
    {"name": "Tempo+ – Wawancara", "url": "https://pustaka-api.tempo.co/single-brand/rss/vip/wawancara", "source_type": SourceType.internal},
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
