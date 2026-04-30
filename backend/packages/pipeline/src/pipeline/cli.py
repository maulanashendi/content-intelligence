import asyncio
import logging
import time

import click
from core.config import settings
from core.logging import configure_logging

logger = logging.getLogger(__name__)

_STEPS = ("ingest", "embed", "cluster", "label", "score")


async def _run_step(step: str) -> None:
    match step:
        case "ingest":
            from ingest.pipeline import run

            result = await run()
            logger.info("ingest complete", extra=result)
        case "embed":
            from embedding.pipeline import run

            count = await run()
            logger.info("embed complete", extra={"count": count})
        case "cluster":
            from clustering.pipeline import run

            await run()
            logger.info("cluster complete")
        case "label":
            from labeling.pipeline import run

            result = await run()
            logger.info("label complete", extra=result)
        case "score":
            from scoring.pipeline import run

            count = await run()
            logger.info("score complete", extra={"cluster_count": count})
        case _:
            raise click.UsageError(f"unknown step: {step}")


@click.group()
def cli() -> None:
    pass


@cli.command("run-daily")
def run_daily() -> None:
    configure_logging(settings.log_level)
    started_at = time.perf_counter()
    logger.info("pipeline started")

    for step in _STEPS:
        step_start = time.perf_counter()
        asyncio.run(_run_step(step))
        logger.info(
            "step finished",
            extra={"step": step, "elapsed_s": round(time.perf_counter() - step_start, 2)},
        )

    logger.info(
        "pipeline finished",
        extra={"total_elapsed_s": round(time.perf_counter() - started_at, 2)},
    )


@cli.command()
@click.argument("step", type=click.Choice(_STEPS))
def run_step(step: str) -> None:
    configure_logging(settings.log_level)
    asyncio.run(_run_step(step))


if __name__ == "__main__":
    cli()
