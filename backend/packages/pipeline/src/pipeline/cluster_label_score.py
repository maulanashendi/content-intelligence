import logging
import uuid
from datetime import UTC, datetime

from core.db import get_session
from core.models import ClusterRun, ClusterRunStage, PipelineStage, StageStatus
from sqlalchemy import update

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _open_stage(run_id: uuid.UUID, stage: PipelineStage) -> uuid.UUID:
    async with get_session() as session:
        row = ClusterRunStage(
            run_id=run_id,
            stage=stage,
            status=StageStatus.running,
            started_at=_now(),
        )
        session.add(row)
        await session.commit()
        return row.id


async def _close_stage(
    stage_id: uuid.UUID,
    status: StageStatus,
    details: dict | None = None,
) -> None:
    async with get_session() as session:
        row = await session.get(ClusterRunStage, stage_id)
        if row is not None:
            row.status = status
            row.finished_at = _now()
            if details is not None:
                row.details = details
            await session.commit()


async def run() -> None:
    from clustering.pipeline import prune_old_cluster_runs
    from clustering.pipeline import run as cluster_run

    # ── cluster ──────────────────────────────────────────────────────
    cluster_started = _now()
    run_id: uuid.UUID | None = await cluster_run()

    if run_id is None:
        logger.info("clustering produced no run, skipping downstream stages")
        return

    async with get_session() as session:
        session.add(
            ClusterRunStage(
                run_id=run_id,
                stage=PipelineStage.cluster,
                status=StageStatus.done,
                started_at=cluster_started,
                finished_at=_now(),
            )
        )
        await session.commit()

    # ── score (SEBELUM label — murah, SQL-only, selalu jalan) ────────
    from scoring.pipeline import run as score_run

    sid = await _open_stage(run_id, PipelineStage.score)
    try:
        count = await score_run()
        logger.info("scoring complete cluster_count=%d", count)
        await _close_stage(sid, StageStatus.done, {"cluster_count": count})
    except Exception:
        logger.exception("scoring stage failed")
        await _close_stage(sid, StageStatus.failed)

    # ── label ─────────────────────────────────────────────────────────
    from labeling.pipeline import run as label_run

    lid = await _open_stage(run_id, PipelineStage.label)
    try:
        result = await label_run()
        logger.info("labeling complete %s", result)
        await _close_stage(lid, StageStatus.done, result)
    except Exception:
        logger.exception("labeling stage failed")
        await _close_stage(lid, StageStatus.failed)

    # ── prune ─────────────────────────────────────────────────────────
    pid = await _open_stage(run_id, PipelineStage.prune)
    try:
        pruned = await prune_old_cluster_runs()
        logger.info("retention complete pruned_runs=%d", pruned)
        await _close_stage(pid, StageStatus.done, {"pruned_runs": pruned})
    except Exception:
        logger.exception("prune stage failed")
        await _close_stage(pid, StageStatus.failed)
        raise

    # ── mark run complete (D36) ────────────────────────────────────────
    # Set finished_at only after scoring + labeling + prune succeed so the
    # scheduler's max(finished_at) check and the API's IS NOT NULL guard both
    # see this run as fully done — a crash mid-labeling no longer looks "done".
    async with get_session() as session:
        await session.execute(
            update(ClusterRun)
            .where(ClusterRun.id == run_id)
            .values(finished_at=_now())
        )
        await session.commit()
    logger.info("cluster run marked finished run_id=%s", run_id)
