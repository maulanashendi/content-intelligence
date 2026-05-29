import logging

logger = logging.getLogger(__name__)


async def run() -> dict[str, int]:
    logger.info("analysis folded into labeling pipeline")
    return {"analyzed": 0, "skipped": 0}
