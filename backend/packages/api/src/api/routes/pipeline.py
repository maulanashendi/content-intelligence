import logging

from core.models import PipelineGroupLock
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text

from api.deps import SessionDep
from api.types import UtcDateTime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_GROUP_INGEST_EMBED = "ingest_embed"
_GROUP_CLUSTER_LABEL_SCORE = "cluster_label_score"
_CHANNEL_INGEST_EMBED = "pipeline_ingest_embed_requested"
_CHANNEL_CLUSTER_LABEL_SCORE = "pipeline_cluster_label_score_requested"


class PipelineTriggerResult(BaseModel):
    group: str
    channel: str
    notified: bool


class PipelineStatusResponse(BaseModel):
    # locked_at timestamp when running, null when idle
    ingest_embed: UtcDateTime | None
    cluster_label_score: UtcDateTime | None


async def _trigger(group: str, channel: str, session: SessionDep) -> PipelineTriggerResult:
    lock = await session.get(PipelineGroupLock, group)
    if lock is not None:
        raise HTTPException(status_code=409, detail=f"Pipeline group {group} sedang berjalan.")

    notified = True
    try:
        await session.execute(
            text("SELECT pg_notify(:channel, :group)"),
            {"channel": channel, "group": group},
        )
        await session.commit()
    except Exception:
        notified = False
        logger.warning("pg_notify failed channel=%s", channel, exc_info=True)

    return PipelineTriggerResult(group=group, channel=channel, notified=notified)


@router.get("/status", response_model=PipelineStatusResponse)
async def pipeline_status(session: SessionDep) -> PipelineStatusResponse:
    locks = (await session.execute(select(PipelineGroupLock))).scalars().all()
    lock_map = {lock.group_name: lock.locked_at for lock in locks}
    return PipelineStatusResponse(
        ingest_embed=lock_map.get(_GROUP_INGEST_EMBED),
        cluster_label_score=lock_map.get(_GROUP_CLUSTER_LABEL_SCORE),
    )


@router.post("/ingest-embed", status_code=202, response_model=PipelineTriggerResult)
async def trigger_ingest_embed(session: SessionDep) -> PipelineTriggerResult:
    return await _trigger(_GROUP_INGEST_EMBED, _CHANNEL_INGEST_EMBED, session)


@router.post("/cluster-label-score", status_code=202, response_model=PipelineTriggerResult)
async def trigger_cluster_label_score(session: SessionDep) -> PipelineTriggerResult:
    return await _trigger(_GROUP_CLUSTER_LABEL_SCORE, _CHANNEL_CLUSTER_LABEL_SCORE, session)
