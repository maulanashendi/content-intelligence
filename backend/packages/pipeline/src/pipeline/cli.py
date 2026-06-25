import asyncio
import logging
import sys
import time
from collections.abc import Callable, Coroutine
from typing import Any

import click
from core.config import settings
from core.logging import configure_logging

from pipeline.locks import GROUP_CLUSTER_LABEL_SCORE, LockHeld, hold_lock

logger = logging.getLogger(__name__)

# ML-heavy steps that must not run concurrently with each other or with the daemon.
# Each step acquires the cluster_label_score group lock so the daemon's embed-defer
# guard also sees the lock (prevents embedder + Gemma collisions at the OS level).
_ML_STEPS = frozenset({"cluster", "label", "score", "cluster-label-score"})


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


async def _analysis() -> dict[str, int]:
    from labeling.analysis import run

    return await run()


async def _gsc() -> None:
    from core.db import get_session
    from ingest import gsc

    async with get_session() as session:
        await gsc.run(session, settings)


async def _prune() -> int:
    from clustering.pipeline import prune_old_cluster_runs

    return await prune_old_cluster_runs()


_STEP_RUNNERS: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {
    "ingest": _ingest,
    "embed": _embed,
    "cluster": _cluster,
    "label": _label,
    "score": _score,
    "analysis": _analysis,
    "gsc": _gsc,
    "prune": _prune,
}


async def _run_step(step: str) -> None:
    if step in _ML_STEPS:
        try:
            async with hold_lock(GROUP_CLUSTER_LABEL_SCORE):
                result = await _STEP_RUNNERS[step]()
        except LockHeld as exc:
            logger.error(
                "ML step blocked: %s",
                exc,
                extra={"step": step},
            )
            sys.exit(1)
    else:
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


@cli.command("cluster-label-score")
def cluster_label_score_cmd() -> None:
    _configure()
    from pipeline.cluster_label_score import run

    async def _run_locked() -> None:
        try:
            async with hold_lock(GROUP_CLUSTER_LABEL_SCORE):
                await run()
        except LockHeld as exc:
            logger.error("cluster-label-score blocked: %s", exc)
            sys.exit(1)

    asyncio.run(_run_locked())


@cli.command("reembed")
def reembed_cmd() -> None:
    _configure()
    from embedding.pipeline import reembed

    async def _run_locked() -> None:
        try:
            async with hold_lock(GROUP_CLUSTER_LABEL_SCORE):
                result = await reembed()
                logger.info("reembed complete", extra={"counts": result})
        except LockHeld as exc:
            logger.error("reembed blocked: %s", exc)
            sys.exit(1)

    asyncio.run(_run_locked())


@cli.command("serve")
def serve() -> None:
    _configure()
    from pipeline.runner import run_loop

    asyncio.run(run_loop())


if __name__ == "__main__":
    cli()
