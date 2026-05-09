import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

_gen_uuid = text("gen_random_uuid()")


class Base(DeclarativeBase):
    pass


class SourceType(enum.Enum):
    rss = "rss"
    internal = "internal"


class SourceStatus(enum.Enum):
    active = "active"
    error = "error"
    blocked = "blocked"


class ScrapeStatus(enum.Enum):
    pending = "pending"
    fast_ok = "fast_ok"
    fast_failed = "fast_failed"
    playwright_ok = "playwright_ok"
    playwright_failed = "playwright_failed"


class ClusterAlgorithm(enum.Enum):
    hdbscan = "hdbscan"
    kmeans = "kmeans"


class ContentSource(Base):
    __tablename__ = "content_source"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    status: Mapped[SourceStatus | None] = mapped_column(Enum(SourceStatus))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    articles: Mapped[list["Article"]] = relationship(back_populates="source")


class Article(Base):
    __tablename__ = "article"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_source.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    first_paragraph: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    scrape_status: Mapped[ScrapeStatus | None] = mapped_column(Enum(ScrapeStatus))
    scrape_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_article_source_id", "source_id"),
        Index("ix_article_published_at", "published_at"),
        Index("ix_article_scrape_status", "scrape_status"),
    )

    source: Mapped["ContentSource"] = relationship(back_populates="articles")
    embedding: Mapped["ArticleEmbedding | None"] = relationship(
        back_populates="article", uselist=False
    )
    gsc_metrics: Mapped[list["ArticleGscMetric"]] = relationship(back_populates="article")
    cluster_memberships: Mapped[list["ArticleClusterMember"]] = relationship(
        back_populates="article"
    )
    trend_signals: Mapped[list["TrendSignalArticle"]] = relationship(back_populates="article")


class ArticleEmbedding(Base):
    __tablename__ = "article_embedding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("article.id"), unique=True, nullable=False
    )
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    article: Mapped["Article"] = relationship(back_populates="embedding")


class ArticleGscMetric(Base):
    __tablename__ = "article_gsc_metric"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("article.id"), nullable=False)
    clicks: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Float)
    avg_position: Mapped[float | None] = mapped_column(Float)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "article_id", "period_start", "period_end", name="uq_gsc_metric_article_period"
        ),
    )

    article: Mapped["Article"] = relationship(back_populates="gsc_metrics")


class GscPage(Base):
    __tablename__ = "gsc_page"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    page_url: Mapped[str] = mapped_column(String, nullable=False)
    clicks: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Float)
    avg_position: Mapped[float | None] = mapped_column(Float)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("page_url", "period_start", "period_end", name="uq_gsc_page_url_period"),
        Index("ix_gsc_page_period_start", "period_start"),
    )


class GscQuery(Base):
    __tablename__ = "gsc_query"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    query: Mapped[str] = mapped_column(String, nullable=False)
    clicks: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Float)
    avg_position: Mapped[float | None] = mapped_column(Float)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("query", "period_start", "period_end", name="uq_gsc_query_period"),
        Index("ix_gsc_query_period_start", "period_start"),
    )


class GscPageQuery(Base):
    __tablename__ = "gsc_page_query"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    page_url: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str] = mapped_column(String, nullable=False)
    clicks: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Float)
    avg_position: Mapped[float | None] = mapped_column(Float)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "page_url", "query", "period_start", "period_end", name="uq_gsc_page_query_period"
        ),
        Index("ix_gsc_page_query_page_url", "page_url"),
        Index("ix_gsc_page_query_period_start", "period_start"),
    )


class TrendSignal(Base):
    __tablename__ = "trend_signal"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    interest_score: Mapped[float | None] = mapped_column(Float)
    region: Mapped[str] = mapped_column(String, server_default="ID", nullable=False)
    category: Mapped[str] = mapped_column(String, server_default="all", nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("keyword", "captured_at", name="uq_trend_signal_keyword_captured_at"),
        Index("ix_trend_signal_captured_at", "captured_at"),
    )

    articles: Mapped[list["TrendSignalArticle"]] = relationship(back_populates="trend_signal")


class TrendSignalArticle(Base):
    __tablename__ = "trend_signal_article"

    trend_signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_signal.id"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("article.id"), primary_key=True)

    __table_args__ = (Index("ix_trend_signal_article_article_id", "article_id"),)

    trend_signal: Mapped["TrendSignal"] = relationship(back_populates="articles")
    article: Mapped["Article"] = relationship(back_populates="trend_signals")


class ClusterRun(Base):
    __tablename__ = "cluster_run"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    algorithm: Mapped[ClusterAlgorithm | None] = mapped_column(Enum(ClusterAlgorithm))
    algorithm_version: Mapped[str | None] = mapped_column(String)
    params: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    clusters: Mapped[list["ArticleCluster"]] = relationship(back_populates="run")


class ArticleCluster(Base):
    __tablename__ = "article_cluster"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cluster_run.id"), nullable=False)
    label: Mapped[str | None] = mapped_column(String)
    centroid: Mapped[list[float] | None] = mapped_column(Vector(768))
    member_count: Mapped[int | None] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_article_cluster_run_id", "run_id"),
        Index("ix_article_cluster_is_current", "is_current"),
    )

    run: Mapped["ClusterRun"] = relationship(back_populates="clusters")
    members: Mapped[list["ArticleClusterMember"]] = relationship(back_populates="cluster")
    insight: Mapped["ClusterInsight | None"] = relationship(back_populates="cluster", uselist=False)


class ArticleClusterMember(Base):
    __tablename__ = "article_cluster_member"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("article_cluster.id"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("article.id"), primary_key=True)
    relevance_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_article_cluster_member_article_id", "article_id"),)

    cluster: Mapped["ArticleCluster"] = relationship(back_populates="members")
    article: Mapped["Article"] = relationship(back_populates="cluster_memberships")


class ClusterInsight(Base):
    __tablename__ = "cluster_insight"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=_gen_uuid
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("article_cluster.id"), unique=True, nullable=False
    )
    trend_velocity: Mapped[float | None] = mapped_column(Float)
    competitor_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    trend_match_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    tempo_covered: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    last_internal_days_ago: Mapped[int | None] = mapped_column(Integer)
    underperformed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    cluster: Mapped["ArticleCluster"] = relationship(back_populates="insight")


class PipelineGroupLock(Base):
    __tablename__ = "pipeline_group_lock"

    # PK is the group name — INSERT uniqueness = race-free lock acquisition.
    # Daemon DELETEs on completion. If the daemon crashes, the row persists
    # and the API returns 409 until an operator clears it (D22).
    group_name: Mapped[str] = mapped_column(String, primary_key=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
