import logging

from ingest.rss import ingest_rss, make_http_client
from ingest.sitemap import ingest_sitemap
from ingest.trends import ingest_trends

logger = logging.getLogger(__name__)


async def run() -> dict:
    totals: dict[str, int] = {}
    async with make_http_client() as client:
        rss_count = await ingest_rss(client)
        totals["rss"] = rss_count
        logger.info("rss: %d articles processed", rss_count)

        sitemap_count = await ingest_sitemap(client)
        totals["sitemap"] = sitemap_count
        logger.info("sitemap: %d articles processed", sitemap_count)

        trends_count = await ingest_trends(client)
        totals["trends"] = trends_count
        logger.info("trends: %d signals processed", trends_count)

    logger.info("ingest complete: %s", totals)
    return totals
