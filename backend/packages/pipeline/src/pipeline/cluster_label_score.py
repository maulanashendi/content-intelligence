import logging

logger = logging.getLogger(__name__)


async def run() -> None:
    from clustering.pipeline import run as cluster_run

    await cluster_run()

    from labeling.pipeline import run as label_run

    await label_run()

    from scoring.pipeline import run as score_run

    count = await score_run()
    logger.info("scoring complete cluster_count=%d", count)
