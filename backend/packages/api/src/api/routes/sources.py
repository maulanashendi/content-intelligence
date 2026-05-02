import logging
import uuid
from datetime import UTC, datetime, timedelta

from core.models import Article, ContentSource, SourceType
from fastapi import APIRouter, HTTPException
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import SessionDep
from api.types import UtcDateTime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    source_type: str
    is_enabled: bool
    status: str | None
    last_fetched_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    article_count_24h: int


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: AnyHttpUrl
    name: str = ""
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def trim_name(cls, v: str) -> str:
        return v.strip()[:200]


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool


def _cutoff_24h() -> datetime:
    return (datetime.now(UTC) - timedelta(hours=24)).replace(tzinfo=None)


async def _count_24h_for_source(session: AsyncSession, source_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count(Article.id)).where(
            Article.source_id == source_id,
            Article.created_at >= _cutoff_24h(),
        )
    )
    return result.scalar_one()


def _serialize(source: ContentSource, article_count_24h: int) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        name=source.name,
        url=source.url,
        source_type=source.source_type.value,
        is_enabled=source.is_enabled,
        status=source.status.value if source.status else None,
        last_fetched_at=source.last_fetched_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
        article_count_24h=article_count_24h,
    )


@router.get("", response_model=list[SourceResponse])
async def list_sources(session: SessionDep) -> list[SourceResponse]:
    count_subq = (
        select(Article.source_id, func.count(Article.id).label("cnt"))
        .where(Article.created_at >= _cutoff_24h())
        .group_by(Article.source_id)
        .subquery()
    )
    stmt = (
        select(ContentSource, func.coalesce(count_subq.c.cnt, 0).label("article_count_24h"))
        .outerjoin(count_subq, count_subq.c.source_id == ContentSource.id)
        .order_by(ContentSource.name.asc())
    )
    rows = (await session.execute(stmt)).all()
    return [_serialize(s, cnt) for s, cnt in rows]


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(body: SourceCreate, session: SessionDep) -> SourceResponse:
    source = ContentSource(
        name=body.name,
        url=str(body.url),
        source_type=SourceType.rss,
        is_enabled=body.is_enabled,
    )
    session.add(source)
    try:
        await session.commit()
        await session.refresh(source)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="URL sudah terdaftar.")

    # Snapshot the response now: a later pg_notify rollback would expire the
    # ORM state and force a sync lazy-load when serializing.
    response = _serialize(source, article_count_24h=0)

    if source.is_enabled:
        # pg_notify is best-effort: a missing/failed listener must not 500 the
        # API. The runner's periodic poll will pick the source up next tick.
        try:
            await session.execute(
                text("SELECT pg_notify('rss_source_created', :id)"),
                {"id": str(response.id)},
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.warning(
                "pg_notify failed for source_id=%s name=%s",
                response.id,
                response.name,
                exc_info=True,
            )

    return response


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: uuid.UUID, session: SessionDep) -> None:
    source = await session.get(ContentSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source tidak ditemukan.")
    count_result = await session.execute(
        select(func.count(Article.id)).where(Article.source_id == source_id)
    )
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=409, detail="Sumber memiliki artikel dan tidak dapat dihapus.")
    await session.delete(source)
    await session.commit()


@router.patch("/{source_id}", response_model=SourceResponse)
async def patch_source(source_id: uuid.UUID, body: SourcePatch, session: SessionDep) -> SourceResponse:
    source = await session.get(ContentSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source tidak ditemukan.")
    source.is_enabled = body.is_enabled
    await session.commit()
    await session.refresh(source)
    return _serialize(source, await _count_24h_for_source(session, source_id))
