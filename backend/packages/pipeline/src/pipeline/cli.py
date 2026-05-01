import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

import click
from core.config import settings
from core.logging import configure_logging

logger = logging.getLogger(__name__)


async def _ingest() -> dict[str, Any]:
    from ingest.pipeline import run

    return await run()


async def _embed() -> int:
    from embedding.pipeline import run

    return await run()


async def _cluster() -> None:
    from clustering.pipeline import run

    await run()


async def _label() -> dict[str, int]:
    from labeling.pipeline import run

    return await run()


async def _score() -> int:
    from scoring.pipeline import run

    return await run()


_STEP_RUNNERS: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
    "ingest": _ingest,
    "embed": _embed,
    "cluster": _cluster,
    "label": _label,
    "score": _score,
}


async def _run_step(step: str) -> None:
    result = await _STEP_RUNNERS[step]()
    logger.info("%s complete", step, extra={"counts": result})


async def _run_daily() -> None:
    started_at = time.perf_counter()
    logger.info("pipeline started")

    for step in _STEP_RUNNERS:
        step_start = time.perf_counter()
        await _run_step(step)
        logger.info(
            "step finished",
            extra={"step": step, "elapsed_s": round(time.perf_counter() - step_start, 2)},
        )

    logger.info(
        "pipeline finished",
        extra={"total_elapsed_s": round(time.perf_counter() - started_at, 2)},
    )


@click.group()
def cli() -> None:
    pass


def _configure() -> None:
    configure_logging(settings.log_level, file_path=settings.log_dir / "pipeline.log")


@cli.command("run-daily")
def run_daily() -> None:
    _configure()
    asyncio.run(_run_daily())


for _step_name in _STEP_RUNNERS:

    def _make_command(name: str) -> None:
        @cli.command(name)
        def _step_cmd() -> None:
            _configure()
            asyncio.run(_run_step(name))

    _make_command(_step_name)


if __name__ == "__main__":
    cli()
