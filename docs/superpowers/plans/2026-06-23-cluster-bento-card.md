# Cluster Bento Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a card-based "bento" view of clusters to `/morning` — compact Tier-1 cards (status, label, velocity) that expand on click to reveal demand/coverage metrics, a 48-hour competitor-volume sparkline, and timestamps, with "Show more (+8)" pagination.

**Architecture:** Two new read-only FastAPI endpoints on the existing `clusters` router (`GET /clusters/bento` for the ranked, paginated card list; `GET /clusters/{id}/volume-trend` for the lazy per-cluster sparkline series). On-read enrichment (internal count, last-article timestamps) — no migration. `views` reuses the existing `cluster_insight.gsc_clicks` column under a scoped reversal of constraint D35. Frontend: new Zod schemas + react-query hooks + a `ClusterBentoCard` feature component reusing the existing design tokens, quadrant color map, `VelocityBar` primitive, and the `volume-chart`/`useElementWidth` patterns.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy async / Pydantic (backend); React 19 / TypeScript / @tanstack/react-query v5 / Zod / d3 / Tailwind + CSS custom properties (frontend); pytest (backend tests), bun:test (frontend tests).

## Global Constraints

- Backend tests need a running Postgres. From `backend/`: `docker compose up -d postgres` once before running tests. Run tests with `cd backend && ./.venv/bin/python -m pytest <path> -v` (host venv per project convention; not `uv run`).
- `api` package never imports ML modules. Within `api`, importing between route modules / shared helpers is allowed.
- API contract = FastAPI `/openapi.json`. Every endpoint change ships Pydantic models + `response_model=` + a one-line `summary=` in the same commit.
- Frontend: cross-feature imports forbidden; new components use Tailwind + CSS vars + `@ei-fe/ui` primitives only — never legacy global classes (`.card`, `.kw-row`). FE typecheck = `cd frontend && bun run build` (runs `tsc -b && vite build`). FE tests = `cd frontend && bun test <path>`.
- No comments explaining WHAT; only non-obvious WHY.
- WIB timezone bucketing is `Asia/Jakarta` (UTC+7). Reuse existing helpers; do not reinvent.
- Commit after every task. Branch off `master` first (do not commit to `master` directly).

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

```bash
cd /home/shendi/self-project/content-intelligence
git checkout -b feat/cluster-bento-card
```

---

### Task 1: Backend — `/clusters/bento` endpoint + scoped D35 reversal (`views`)

**Files:**
- Modify: `backend/packages/api/src/api/routes/clusters.py` (add `SourceType` import, `_ranking_order()` helper, refactor `morning_clusters` to use it, add `BentoCard`/`BentoListResponse` models, add `/bento` route)
- Test: `backend/packages/api/tests/test_clusters_bento.py` (create)
- Modify: `backend/packages/api/tests/test_clusters_no_gsc_leak.py` (extend coverage to `/bento` + positive `views` assertion)
- Modify (docs): `docs/constraints.md`, `CLAUDE.md`, `docs/decisions.md`

**Interfaces:**
- Produces (consumed by Task 3's Zod schema): `BentoCard { id: uuid, label: str|None, editorial_quadrant: str|None, trend_velocity: float|None, competitor_count: int|None, trend_match_count: int|None, member_count: int|None, views: int, internal_article_count: int, last_competitor_at: datetime|None, last_internal_at: datetime|None }` and `BentoListResponse { cards: list[BentoCard], total: int, served_at: datetime|None, is_stale: bool, max_age_hours: int }`.
- Endpoint: `GET /api/v1/clusters/bento?limit=8&offset=0`.

- [ ] **Step 1: Write the failing tests**

Create `backend/packages/api/tests/test_clusters_bento.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ClusterRun,
    ContentSource,
    SourceType,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType, name: str) -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name=name,
        url=f"https://test-{uuid.uuid4()}.com",
        source_type=source_type,
    )


def _article(source_id: uuid.UUID, published_at: datetime) -> Article:
    return Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title="Test Article",
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )


def _cluster_insight(
    run_id: uuid.UUID,
    *,
    tempo_covered: bool = False,
    editorial_quadrant: str | None = "opportunity",
    demand_score: float | None = 0.5,
    gsc_clicks: int = 0,
    member_count: int | None = 1,
) -> tuple[ArticleCluster, ClusterInsight]:
    cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_id,
        label="Test",
        is_current=True,
        member_count=member_count,
    )
    insight = ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster.id,
        trend_velocity=0.5,
        competitor_count=2,
        trend_match_count=1,
        tempo_covered=tempo_covered,
        editorial_quadrant=editorial_quadrant,
        demand_score=demand_score,
        gsc_clicks=gsc_clicks,
    )
    return cluster, insight


async def test_bento_includes_all_quadrants_unlike_morning(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    covered, covered_i = _cluster_insight(
        run.id, tempo_covered=True, editorial_quadrant="winning"
    )
    session.add_all([run, covered, covered_i])
    await session.flush()

    bento_ids = [c["id"] for c in (await client.get("/api/v1/clusters/bento")).json()["cards"]]
    morning_ids = [c["id"] for c in (await client.get("/api/v1/clusters/morning")).json()["clusters"]]
    assert str(covered.id) in bento_ids
    assert str(covered.id) not in morning_ids


async def test_bento_ranks_opportunity_then_demand(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    c1, i1 = _cluster_insight(run.id, editorial_quadrant="opportunity", demand_score=0.9)
    c2, i2 = _cluster_insight(run.id, editorial_quadrant="opportunity", demand_score=0.5)
    c3, i3 = _cluster_insight(run.id, editorial_quadrant="ignore", demand_score=0.0)
    session.add_all([run, c1, i1, c2, i2, c3, i3])
    await session.flush()

    ids = [c["id"] for c in (await client.get("/api/v1/clusters/bento")).json()["cards"]]
    assert ids.index(str(c1.id)) < ids.index(str(c2.id)) < ids.index(str(c3.id))


async def test_bento_pagination_offset_limit_and_total(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    items = []
    # Distinct demand_score => fully deterministic order, highest first.
    for n in range(5):
        c, i = _cluster_insight(run.id, demand_score=0.9 - n * 0.1)
        items += [c, i]
    session.add_all([run, *items])
    await session.flush()

    page1 = (await client.get("/api/v1/clusters/bento?limit=2&offset=0")).json()
    page2 = (await client.get("/api/v1/clusters/bento?limit=2&offset=2")).json()
    assert page1["total"] == 5
    assert len(page1["cards"]) == 2
    assert len(page2["cards"]) == 2
    p1_ids = {c["id"] for c in page1["cards"]}
    p2_ids = {c["id"] for c in page2["cards"]}
    assert p1_ids.isdisjoint(p2_ids)


async def test_bento_exposes_views_from_gsc_clicks(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_insight(run.id, gsc_clicks=1234)
    session.add_all([run, cluster, insight])
    await session.flush()

    card = (await client.get("/api/v1/clusters/bento")).json()["cards"][0]
    assert card["views"] == 1234


async def test_bento_internal_count_and_timestamps(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_insight(run.id, member_count=3)
    rss = _source(SourceType.rss, "Kompas")
    internal = _source(SourceType.internal, "Tempo")
    comp_old = _article(rss.id, _NOW - timedelta(hours=10))
    comp_new = _article(rss.id, _NOW - timedelta(hours=2))
    internal_a = _article(internal.id, _NOW - timedelta(hours=5))
    session.add_all([run, cluster, insight, rss, internal, comp_old, comp_new, internal_a])
    await session.flush()
    session.add_all([
        ArticleClusterMember(id=uuid.uuid4(), cluster_id=cluster.id, article_id=comp_old.id),
        ArticleClusterMember(id=uuid.uuid4(), cluster_id=cluster.id, article_id=comp_new.id),
        ArticleClusterMember(id=uuid.uuid4(), cluster_id=cluster.id, article_id=internal_a.id),
    ])
    await session.flush()

    card = (await client.get("/api/v1/clusters/bento")).json()["cards"][0]
    assert card["internal_article_count"] == 1
    assert card["last_competitor_at"] is not None
    assert card["last_internal_at"] is not None
    # last_competitor_at is the newer of the two competitor articles
    assert card["last_competitor_at"] > card["last_internal_at"]


async def test_bento_zero_members_defaults(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_insight(run.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    card = (await client.get("/api/v1/clusters/bento")).json()["cards"][0]
    assert card["internal_article_count"] == 0
    assert card["last_competitor_at"] is None
    assert card["last_internal_at"] is None


async def test_bento_empty_when_no_run(client: AsyncClient) -> None:
    data = (await client.get("/api/v1/clusters/bento")).json()
    assert data["cards"] == []
    assert data["total"] == 0
    assert data["is_stale"] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_clusters_bento.py -v
```
Expected: FAIL — `/api/v1/clusters/bento` returns 404 (route not defined).

- [ ] **Step 3: Add the `SourceType` import**

In `backend/packages/api/src/api/routes/clusters.py`, change the `core.models` import block (lines 6-14) to add `SourceType`:

```python
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ClusterRun,
    ClusterRunStage,
    ContentSource,
    SourceType,
)
```

- [ ] **Step 4: Add the shared `_ranking_order()` helper and refactor `morning_clusters`**

In `clusters.py`, add this helper right after `_leaf_guard()` (after line 140):

```python
def _ranking_order() -> list:
    """Shared ORDER BY for morning + bento so the two ranking surfaces cannot drift.

    The trailing ArticleCluster.id is a stable tiebreaker required for correct
    offset pagination on /bento.
    """
    return [
        (ClusterInsight.editorial_quadrant == "opportunity").desc(),
        ClusterInsight.demand_score.desc().nullslast(),
        ClusterInsight.trend_match_count.desc(),
        ArticleCluster.member_count.desc().nullslast(),
        ArticleCluster.id,
    ]
```

Then in `morning_clusters` replace the `.order_by(...)` block (lines 269-275) with:

```python
        .order_by(*_ranking_order())
```

- [ ] **Step 5: Add the bento Pydantic models**

In `clusters.py`, add after `ClusterListResponse` (after line 56):

```python
class BentoCard(BaseModel):
    id: uuid.UUID
    label: str | None
    editorial_quadrant: str | None
    trend_velocity: float | None
    competitor_count: int | None
    trend_match_count: int | None
    member_count: int | None
    views: int
    internal_article_count: int
    last_competitor_at: UtcDateTime | None
    last_internal_at: UtcDateTime | None


class BentoListResponse(BaseModel):
    cards: list[BentoCard]
    total: int
    served_at: UtcDateTime | None
    is_stale: bool
    max_age_hours: int
```

- [ ] **Step 6: Add the `/bento` route**

In `clusters.py`, add this route immediately after `morning_clusters` (after line 286). It must be declared before the `/{cluster_id}` route (which is last in the file, so any position above it is fine):

```python
@router.get("/bento", response_model=BentoListResponse, summary="All current clusters ranked, paginated, for the bento card grid")
async def bento_clusters(
    session: SessionDep,
    limit: int = Query(default=8, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> BentoListResponse:
    run_filter = _resolve_cluster_filter()
    base_where = (run_filter, _leaf_guard())

    total: int = (
        await session.execute(
            select(func.count())
            .select_from(ArticleCluster)
            .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
            .where(*base_where)
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(ArticleCluster, ClusterInsight)
            .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
            .where(*base_where)
            .order_by(*_ranking_order())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    page_ids = [cluster.id for cluster, _ in rows]
    enrich: dict[uuid.UUID, Any] = {}
    if page_ids:
        effective = func.coalesce(Article.published_at, Article.created_at)
        enrich_rows = (
            await session.execute(
                select(
                    ArticleClusterMember.cluster_id.label("cid"),
                    func.count()
                    .filter(ContentSource.source_type == SourceType.internal)
                    .label("internal_count"),
                    func.max(effective)
                    .filter(ContentSource.source_type == SourceType.rss)
                    .label("last_competitor_at"),
                    func.max(effective)
                    .filter(ContentSource.source_type == SourceType.internal)
                    .label("last_internal_at"),
                )
                .select_from(ArticleClusterMember)
                .join(Article, Article.id == ArticleClusterMember.article_id)
                .join(ContentSource, ContentSource.id == Article.source_id)
                .where(ArticleClusterMember.cluster_id.in_(page_ids))
                .group_by(ArticleClusterMember.cluster_id)
            )
        ).all()
        enrich = {r.cid: r for r in enrich_rows}

    cards = [
        BentoCard(
            id=cluster.id,
            label=cluster.label,
            editorial_quadrant=insight.editorial_quadrant,
            trend_velocity=insight.trend_velocity,
            competitor_count=insight.competitor_count,
            trend_match_count=insight.trend_match_count,
            member_count=cluster.member_count,
            views=insight.gsc_clicks,
            internal_article_count=(enrich[cluster.id].internal_count if cluster.id in enrich else 0),
            last_competitor_at=(enrich[cluster.id].last_competitor_at if cluster.id in enrich else None),
            last_internal_at=(enrich[cluster.id].last_internal_at if cluster.id in enrich else None),
        )
        for cluster, insight in rows
    ]
    served_at = await _get_served_at(session, run_filter)
    return BentoListResponse(
        cards=cards,
        total=total,
        served_at=served_at,
        is_stale=_compute_is_stale(served_at),
        max_age_hours=settings.cluster_staleness_max_age_hours,
    )
```

- [ ] **Step 7: Run the bento tests to verify they pass**

```bash
cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_clusters_bento.py -v
```
Expected: PASS (all 7 tests).

- [ ] **Step 8: Run the existing cluster tests to confirm the morning refactor didn't regress**

```bash
cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_clusters.py -v
```
Expected: PASS.

- [ ] **Step 9: Extend the GSC-leak guard for `/bento`**

In `backend/packages/api/tests/test_clusters_no_gsc_leak.py`, change the `list_paths` list (currently `/morning`, `/current`, `/deferred`) to also include the bento endpoint, and add a positive `views` assertion. Replace the `list_paths` block and add the assertion after the existing detail block:

```python
    list_paths = [
        "/api/v1/clusters/morning",
        "/api/v1/clusters/current",
        "/api/v1/clusters/deferred",
        "/api/v1/clusters/bento",
    ]
    for path in list_paths:
        response = await client.get(path)
        assert response.status_code == 200, path
        for field in _RAW_GSC_FIELDS:
            assert field not in response.text, f"raw GSC field {field} leaked by {path}"

    # D38: bento exposes aggregated clicks as `views` (never the raw `gsc_clicks` name).
    bento = (await client.get("/api/v1/clusters/bento")).json()
    assert bento["cards"], "expected the seeded cluster as a bento card"
    assert "views" in bento["cards"][0]
```

- [ ] **Step 10: Run the leak test**

```bash
cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_clusters_no_gsc_leak.py -v
```
Expected: PASS.

- [ ] **Step 11: Amend the constraint docs (D35 → scoped reversal D38)**

In `docs/constraints.md` line 73, replace the bullet with:

```markdown
- **GSC metrics are reference-only, except aggregated clicks (D35, amended D38).** `article_gsc_metric` rows and the raw GSC aggregate columns `gsc_impressions`, `gsc_ctr`, `gsc_avg_position` in `cluster_insight` are internal scoring inputs only — never returned in API responses. **Exception (D38):** `cluster_insight.gsc_clicks` may be returned as an aggregated per-cluster `views` figure on `/clusters/bento`. Derived editorial levels (`demand_score`, `high_demand`, `performance_level`, `editorial_quadrant`) are signals, not raw metrics, and may be returned.
```

In `docs/constraints.md` line 14, replace `This app does not display raw GSC numbers (clicks, impressions, position, CTR).` with:

```markdown
This app does not display raw GSC numbers (impressions, position, CTR); aggregated per-cluster clicks are surfaced as `views` on the cluster bento (D38).
```

In `docs/constraints.md` line 20, replace the bullet with:

```markdown
- Raw internal article performance metrics (impressions, position, CTR) displayed in the UI — aggregated per-cluster clicks as `views` are permitted on the bento (D38); derived editorial levels are permitted per D35
```

In `CLAUDE.md` line 67, replace the bullet with:

```markdown
- GSC metrics are scoring inputs only — never returned via API, **except** aggregated per-cluster clicks exposed as `views` on `/clusters/bento` (D38). Impressions/CTR/position stay internal.
```

In `CLAUDE.md`, in the "API endpoints" section, update the "Live read endpoints" sentence to include the two new paths: add `/api/v1/clusters/bento` and `/api/v1/clusters/{id}/volume-trend` to the list.

- [ ] **Step 12: Record decision D38**

Append to `docs/decisions.md` (after the D37 section):

```markdown
## D38. Expose aggregated per-cluster GSC clicks as `views` on the bento (scoped reversal of D35)

The cluster bento card surfaces editorial pull-through with a `views` tile. The
only traffic signal in the system is GSC, which D35 keeps internal. We reverse
D35 **narrowly**: `cluster_insight.gsc_clicks` (already de-duplicated to one GSC
period per article during scoring) is returned as an aggregated per-cluster
`views` integer on `GET /clusters/bento` only. Impressions, CTR, and average
position remain internal scoring inputs and are still asserted absent from every
response by `test_clusters_no_gsc_leak.py`. No new column, no migration — the
existing aggregate is un-hidden under a non-raw field name.
```

- [ ] **Step 13: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/api/src/api/routes/clusters.py \
        backend/packages/api/tests/test_clusters_bento.py \
        backend/packages/api/tests/test_clusters_no_gsc_leak.py \
        docs/constraints.md CLAUDE.md docs/decisions.md
git commit -m "feat(api): /clusters/bento endpoint + scoped D35 reversal for views

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Backend — per-cluster `/clusters/{id}/volume-trend` (lazy sparkline series)

**Files:**
- Create: `backend/packages/api/src/api/volume.py` (shared volume schema + bucketing helpers, moved out of `articles.py`)
- Modify: `backend/packages/api/src/api/routes/articles.py` (import the moved symbols)
- Modify: `backend/packages/api/src/api/routes/clusters.py` (add the per-cluster route)
- Test: `backend/packages/api/tests/test_cluster_volume_trend.py` (create)

**Interfaces:**
- Consumes (from Task 1): nothing new.
- Produces: `GET /api/v1/clusters/{cluster_id}/volume-trend?bucket=hour|day` returning the existing `VolumeTrendResponse` shape (`{ bucket, buckets: [{bucket_start, competitor_count, internal_count}], generated_at }`), scoped to one cluster's members. Task 3's chart reuses the existing `VolumeTrendResponseSchema`.

- [ ] **Step 1: Write the failing tests**

Create `backend/packages/api/tests/test_cluster_volume_trend.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterRun,
    ContentSource,
    SourceType,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType, name: str) -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name=name,
        url=f"https://test-{uuid.uuid4()}.com",
        source_type=source_type,
    )


def _article(source_id: uuid.UUID, published_at: datetime) -> Article:
    return Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title="A",
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )


async def test_cluster_volume_trend_404_for_unknown_id(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/clusters/{uuid.uuid4()}/volume-trend?bucket=hour")
    assert r.status_code == 404


async def test_cluster_volume_trend_hour_has_48_buckets(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    session.add_all([run, cluster])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    assert d["bucket"] == "hour"
    assert len(d["buckets"]) == 48
    assert all(b["competitor_count"] == 0 and b["internal_count"] == 0 for b in d["buckets"])


async def test_cluster_volume_trend_counts_only_this_clusters_members(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    other = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="Other", is_current=True)
    rss = _source(SourceType.rss, "Kompas")
    internal = _source(SourceType.internal, "Tempo")
    ts = _NOW - timedelta(hours=2)
    a_comp = _article(rss.id, ts)
    a_int = _article(internal.id, ts)
    a_other = _article(rss.id, ts)
    session.add_all([run, cluster, other, rss, internal, a_comp, a_int, a_other])
    await session.flush()
    session.add_all([
        ArticleClusterMember(id=uuid.uuid4(), cluster_id=cluster.id, article_id=a_comp.id),
        ArticleClusterMember(id=uuid.uuid4(), cluster_id=cluster.id, article_id=a_int.id),
        ArticleClusterMember(id=uuid.uuid4(), cluster_id=other.id, article_id=a_other.id),
    ])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    assert sum(b["competitor_count"] for b in d["buckets"]) == 1
    assert sum(b["internal_count"] for b in d["buckets"]) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_cluster_volume_trend.py -v
```
Expected: FAIL — route returns 404 / not defined (the 404 test may pass by accident; the other two fail).

- [ ] **Step 3: Create the shared volume module**

Create `backend/packages/api/src/api/volume.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Literal

from api.types import UtcDateTime
from pydantic import BaseModel

_WIB = timezone(timedelta(hours=7))
_RANGE: dict[str, tuple[timedelta, int]] = {
    "hour": (timedelta(hours=1), 48),
    "day": (timedelta(days=1), 30),
}


class VolumeBucket(BaseModel):
    bucket_start: UtcDateTime
    competitor_count: int
    internal_count: int


class VolumeTrendResponse(BaseModel):
    bucket: Literal["hour", "day"]
    buckets: list[VolumeBucket]
    generated_at: UtcDateTime


def dense_bucket_starts(bucket: Literal["hour", "day"], now_utc: datetime) -> list[datetime]:
    """Naive WIB wall-clock bucket starts, oldest→newest, covering the range."""
    step, count = _RANGE[bucket]
    now_wib = now_utc.astimezone(_WIB).replace(tzinfo=None)
    if bucket == "hour":
        current = now_wib.replace(minute=0, second=0, microsecond=0)
    else:
        current = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    return [current - step * i for i in range(count - 1, -1, -1)]
```

- [ ] **Step 4: Refactor `articles.py` to use the shared module**

In `backend/packages/api/src/api/routes/articles.py`:

Remove the now-moved definitions — delete the `_WIB`/`_RANGE` block (lines 36-40), the `VolumeBucket` class (lines 43-47), the `VolumeTrendResponse` class (lines 49-52), and the `_dense_bucket_starts` function (lines 55-63).

Add this import near the top (after line 12):

```python
from api.volume import VolumeBucket, VolumeTrendResponse, dense_bucket_starts
```

In `volume_trend`, change the call `starts_wib = _dense_bucket_starts(bucket, now_utc)` to `starts_wib = dense_bucket_starts(bucket, now_utc)`.

(`math`, `timezone`, and `timedelta` may now be unused at module import — keep `timedelta`/`UTC`/`datetime`; remove `timezone` from the datetime import and remove `import math` only if no longer referenced. Verify with the build/test run below.)

- [ ] **Step 5: Add the per-cluster route to `clusters.py`**

In `clusters.py`, add this import near the other `api.*` imports (after line 21):

```python
from api.volume import VolumeBucket, VolumeTrendResponse, dense_bucket_starts
```

Add `Literal` to the `typing` import (line 3 is `from typing import Any, Literal` — it already includes `Literal`, no change needed).

Add this route immediately before the `/{cluster_id}` route (before line 410):

```python
@router.get(
    "/{cluster_id}/volume-trend",
    response_model=VolumeTrendResponse,
    summary="Competitor vs internal article volume per WIB bucket, scoped to one cluster",
)
async def cluster_volume_trend(
    cluster_id: uuid.UUID,
    session: SessionDep,
    bucket: Literal["hour", "day"] = Query("hour"),
) -> VolumeTrendResponse:
    exists_row = (
        await session.execute(select(ArticleCluster.id).where(ArticleCluster.id == cluster_id))
    ).scalar_one_or_none()
    if exists_row is None:
        raise HTTPException(status_code=404, detail="Cluster not found")

    now_utc = datetime.now(UTC)
    starts_wib = dense_bucket_starts(bucket, now_utc)
    cutoff_utc = starts_wib[0] - timedelta(hours=7)

    effective = func.coalesce(Article.published_at, Article.created_at)
    wib_local = func.timezone("Asia/Jakarta", func.timezone("UTC", effective))
    wib_bucket = func.date_trunc(bucket, wib_local)

    stmt = (
        select(
            wib_bucket.label("wib_bucket"),
            ContentSource.source_type.label("source_type"),
            func.count(Article.id).label("cnt"),
        )
        .select_from(ArticleClusterMember)
        .join(Article, Article.id == ArticleClusterMember.article_id)
        .join(ContentSource, ContentSource.id == Article.source_id)
        .where(ArticleClusterMember.cluster_id == cluster_id, effective >= cutoff_utc)
        .group_by(wib_bucket, ContentSource.source_type)
    )
    rows = (await session.execute(stmt)).all()
    counts: dict[tuple[datetime, SourceType], int] = {
        (r.wib_bucket, r.source_type): r.cnt for r in rows
    }

    buckets = [
        VolumeBucket(
            bucket_start=start - timedelta(hours=7),
            competitor_count=counts.get((start, SourceType.rss), 0),
            internal_count=counts.get((start, SourceType.internal), 0),
        )
        for start in starts_wib
    ]
    return VolumeTrendResponse(bucket=bucket, buckets=buckets, generated_at=now_utc)
```

- [ ] **Step 6: Run all affected backend tests to verify they pass**

```bash
cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_cluster_volume_trend.py packages/api/tests/test_volume_trend.py packages/api/tests/test_clusters.py -v
```
Expected: PASS (new per-cluster tests + the unchanged global volume-trend tests + cluster tests).

- [ ] **Step 7: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/api/src/api/volume.py \
        backend/packages/api/src/api/routes/articles.py \
        backend/packages/api/src/api/routes/clusters.py \
        backend/packages/api/tests/test_cluster_volume_trend.py
git commit -m "feat(api): per-cluster /clusters/{id}/volume-trend; share volume helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — Zod schemas, query keys, hooks

**Files:**
- Modify: `frontend/packages/api/src/schemas.ts` (add `BentoCardSchema`, `BentoListResponseSchema`)
- Modify: `frontend/packages/api/src/keys.ts` (add `clusterKeys.bento`, `clusterKeys.volumeTrend`)
- Modify: `frontend/packages/api/src/queries.ts` (add `useClusterBento`, `useClusterVolumeTrend`)
- Test: `frontend/packages/api/tests/bento-schemas.test.ts` (create)

**Interfaces:**
- Consumes (from Task 1/2): the `/clusters/bento` and `/clusters/{id}/volume-trend` JSON shapes.
- Produces (for Task 6): `useClusterBento(limit: number)` → react-query result of `BentoListResponse`; `useClusterVolumeTrend(id: string, enabled: boolean)` → react-query result of `VolumeTrendResponse`; types `BentoCard`, `BentoListResponse`.

- [ ] **Step 1: Write the failing schema test**

Create `frontend/packages/api/tests/bento-schemas.test.ts`:

```typescript
import { describe, test, expect } from "bun:test"
import { BentoCardSchema, BentoListResponseSchema } from "../src/schemas.js"

const VALID_CARD = {
  id: "a1b2c3d4-0001-4000-8000-000000000001",
  label: "Koalisi partai jelang Pilpres 2029",
  editorial_quadrant: "opportunity",
  trend_velocity: 1.84,
  competitor_count: 12,
  trend_match_count: 8,
  member_count: 47,
  views: 12450,
  internal_article_count: 3,
  last_competitor_at: "2026-06-23T05:00:00Z",
  last_internal_at: null,
}

describe("BentoCardSchema", () => {
  test("accepts a valid card", () => {
    expect(BentoCardSchema.safeParse(VALID_CARD).success).toBe(true)
  })
  test("rejects a card missing views", () => {
    const { views: _views, ...noViews } = VALID_CARD
    expect(BentoCardSchema.safeParse(noViews).success).toBe(false)
  })
})

describe("BentoListResponseSchema", () => {
  test("accepts a valid envelope", () => {
    const ok = BentoListResponseSchema.safeParse({
      cards: [VALID_CARD],
      total: 1,
      served_at: "2026-06-23T05:00:00Z",
      is_stale: false,
      max_age_hours: 36,
    })
    expect(ok.success).toBe(true)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && bun test packages/api/tests/bento-schemas.test.ts
```
Expected: FAIL — `BentoCardSchema` is not exported.

- [ ] **Step 3: Add the schemas**

In `frontend/packages/api/src/schemas.ts`, add after `ClusterListResponseSchema` (after line 71):

```typescript
export const BentoCardSchema = z.object({
  id: z.string().uuid(),
  label: z.string().nullable(),
  editorial_quadrant: z.string().nullable(),
  trend_velocity: z.number().nullable(),
  competitor_count: z.number().int().nullable(),
  trend_match_count: z.number().int().nullable(),
  member_count: z.number().int().nullable(),
  views: z.number().int(),
  internal_article_count: z.number().int(),
  last_competitor_at: z.string().nullable(),
  last_internal_at: z.string().nullable(),
})
export type BentoCard = z.infer<typeof BentoCardSchema>

export const BentoListResponseSchema = z.object({
  cards: z.array(BentoCardSchema),
  total: z.number().int(),
  served_at: z.string().datetime().nullable(),
  is_stale: z.boolean(),
  max_age_hours: z.number().int(),
})
export type BentoListResponse = z.infer<typeof BentoListResponseSchema>
```

- [ ] **Step 4: Run the schema test to verify it passes**

```bash
cd frontend && bun test packages/api/tests/bento-schemas.test.ts
```
Expected: PASS.

- [ ] **Step 5: Add the query keys**

In `frontend/packages/api/src/keys.ts`, add two entries to `clusterKeys` (inside the object, after `byQuadrant`):

```typescript
  bento: (limit: number) => [...clusterKeys.all, "bento", limit] as const,
  volumeTrend: (id: string) => [...clusterKeys.all, "volume-trend", id] as const,
```

- [ ] **Step 6: Add the hooks**

In `frontend/packages/api/src/queries.ts`:

Change the react-query import on line 1 to add `keepPreviousData`:

```typescript
import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query"
```

Add `BentoListResponseSchema` to the schema import on line 4 (append it to the existing `{ ... }` list).

Append these hooks at the end of the file:

```typescript
export function useClusterBento(limit: number) {
  return useQuery({
    queryKey: clusterKeys.bento(limit),
    queryFn: () => apiGet(`/clusters/bento?limit=${limit}&offset=0`, BentoListResponseSchema),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
  })
}

export function useClusterVolumeTrend(id: string, enabled: boolean) {
  return useQuery({
    queryKey: clusterKeys.volumeTrend(id),
    queryFn: () => apiGet(`/clusters/${id}/volume-trend?bucket=hour`, VolumeTrendResponseSchema),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}
```

- [ ] **Step 7: Typecheck**

```bash
cd frontend && bun run build
```
Expected: build succeeds (no type errors).

- [ ] **Step 8: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/api/src/schemas.ts \
        frontend/packages/api/src/keys.ts \
        frontend/packages/api/src/queries.ts \
        frontend/packages/api/tests/bento-schemas.test.ts
git commit -m "feat(fe-api): bento schemas + useClusterBento/useClusterVolumeTrend hooks

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Frontend — single-series sparkline builder

**Files:**
- Create: `frontend/packages/features/src/morning/sparkline.ts`
- Test: `frontend/packages/features/tests/sparkline.test.ts` (create)

**Interfaces:**
- Produces (for Task 6): `buildSparkline(values: number[], dims: SparklineDims): SparklineModel` where `SparklineDims = { width, height, pad }` and `SparklineModel = { linePath: string, areaPath: string, lastX: number, lastY: number }`. Empty `values` → empty path strings and `lastX/lastY = 0`.

- [ ] **Step 1: Write the failing test**

Create `frontend/packages/features/tests/sparkline.test.ts`:

```typescript
import { describe, test, expect } from "bun:test"
import { buildSparkline } from "../src/morning/sparkline.js"

const DIMS = { width: 200, height: 50, pad: 4 }

describe("buildSparkline", () => {
  test("empty values produce empty paths", () => {
    const m = buildSparkline([], DIMS)
    expect(m.linePath).toBe("")
    expect(m.areaPath).toBe("")
  })

  test("line path starts with a moveto and has one segment per point", () => {
    const m = buildSparkline([1, 2, 3], DIMS)
    expect(m.linePath.startsWith("M")).toBe(true)
    expect((m.linePath.match(/L/g) ?? []).length).toBe(2)
  })

  test("higher values map to smaller y (inverted screen axis)", () => {
    const m = buildSparkline([0, 10], DIMS)
    // last point is the max → its y is the top (smaller) within padding
    expect(m.lastY).toBeCloseTo(DIMS.pad, 5)
  })

  test("area path closes back to the baseline", () => {
    const m = buildSparkline([1, 2], DIMS)
    expect(m.areaPath.endsWith("Z")).toBe(true)
  })

  test("single point still yields a valid line path", () => {
    const m = buildSparkline([5], DIMS)
    expect(m.linePath.startsWith("M")).toBe(true)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && bun test packages/features/tests/sparkline.test.ts
```
Expected: FAIL — module `sparkline.js` not found.

- [ ] **Step 3: Implement the builder**

Create `frontend/packages/features/src/morning/sparkline.ts`:

```typescript
import { scaleLinear } from "d3"

export interface SparklineDims {
  width: number
  height: number
  pad: number
}

export interface SparklineModel {
  linePath: string
  areaPath: string
  lastX: number
  lastY: number
}

export function buildSparkline(values: number[], dims: SparklineDims): SparklineModel {
  if (values.length === 0) {
    return { linePath: "", areaPath: "", lastX: 0, lastY: 0 }
  }

  const { width, height, pad } = dims
  const max = Math.max(...values)
  const min = Math.min(...values)
  const x = scaleLinear()
    .domain([0, Math.max(1, values.length - 1)])
    .range([pad, width - pad])
  const y = scaleLinear()
    .domain([min, max === min ? min + 1 : max])
    .range([height - pad, pad])

  const points = values.map((v, i) => [x(i), y(v)] as const)
  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(2)} ${p[1].toFixed(2)}`)
    .join(" ")
  const baseline = height - pad
  const first = points[0]
  const last = points[points.length - 1]
  const areaPath = `${linePath} L${last[0].toFixed(2)} ${baseline.toFixed(2)} L${first[0].toFixed(2)} ${baseline.toFixed(2)} Z`

  return { linePath, areaPath, lastX: last[0], lastY: last[1] }
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd frontend && bun test packages/features/tests/sparkline.test.ts
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/features/src/morning/sparkline.ts \
        frontend/packages/features/tests/sparkline.test.ts
git commit -m "feat(fe): single-series sparkline path builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — extract the shared quadrant map

**Files:**
- Create: `frontend/packages/features/src/morning/quadrants.ts`
- Modify: `frontend/packages/features/src/morning/opportunity-matrix-card.tsx` (import from the new module instead of defining inline)

**Interfaces:**
- Produces (for Task 6 + opportunity-matrix): `QUADRANTS: QuadrantDef[]`, `TOO_EARLY_DEF`, `type Quadrant`, `type QuadrantDef`, and `QUADRANT_BY_KEY: Record<string, QuadrantDef | typeof TOO_EARLY_DEF>` for lookup by `editorial_quadrant` string.

This is a pure refactor — no behavior change. Verified by the build passing and the matrix still rendering unchanged.

- [ ] **Step 1: Create the shared module**

Create `frontend/packages/features/src/morning/quadrants.ts` by moving the type + data out of `opportunity-matrix-card.tsx` and adding a lookup:

```typescript
import type { QuadrantSummary } from "@ei-fe/api"

export type Quadrant = keyof Omit<QuadrantSummary, "total">

export interface QuadrantDef {
  key: Quadrant
  emoji: string
  label: string
  sub: string
  action: string
  description: string
  bg: string
  activeBg: string
  border: string
  activeBorder: string
  countColor: string
  highlight?: boolean
}

export const QUADRANTS: QuadrantDef[] = [
  {
    key: "opportunity",
    emoji: "🔥",
    label: "Peluang",
    sub: "Dicari, belum ditulis",
    action: "Tulis sekarang",
    description:
      "Topik ini sedang banyak dicari di luar — tren aktif, kompetitor giat menulis — tapi Tempo belum punya liputannya atau sangat tipis. Ini celah kompetitif yang nyata: editor lain sudah bergerak, pembaca sudah mencarinya.",
    bg: "var(--warn-soft)",
    activeBg: "var(--warn)",
    border: "var(--warn)",
    activeBorder: "var(--warn)",
    countColor: "var(--warn)",
    highlight: true,
  },
  {
    key: "winning",
    emoji: "✅",
    label: "Menang",
    sub: "Dicari, sudah kuat",
    action: "Pertahankan",
    description:
      "Topik ini sudah kuat di kedua sisi: banyak dicari di luar dan Tempo punya liputan yang bagus. Pertahankan konsistensi publikasi. Memperdalam atau memperbarui artikel yang ada bisa memaksimalkan potensi.",
    bg: "var(--ok-soft)",
    activeBg: "var(--ok)",
    border: "var(--ok)",
    activeBorder: "var(--ok)",
    countColor: "var(--ok)",
  },
  {
    key: "ignore",
    emoji: "💤",
    label: "Abaikan",
    sub: "Sepi, belum ditulis",
    action: "Tidak mendesak",
    description:
      "Topik ini sepi dari sisi eksternal — sedikit tren, sedikit kompetitor — dan Tempo belum meliputnya. Tidak ada urgensi editorial. Bisa dikerjakan belakangan atau tidak sama sekali jika ada topik lebih penting.",
    bg: "var(--bg-sunken)",
    activeBg: "var(--line-strong)",
    border: "var(--line)",
    activeBorder: "var(--line-strong)",
    countColor: "var(--fg-muted)",
  },
  {
    key: "evergreen",
    emoji: "🪦",
    label: "Evergreen",
    sub: "Sepi, sudah kuat",
    action: "Biarkan bekerja",
    description:
      "Topik ini tidak sedang trending, tapi Tempo punya liputan yang solid di mesin pencari. Biarkan bekerja sendiri — artikel sudah mendapat trafik organik. Pertimbangkan refresh hanya jika ada angle baru yang signifikan.",
    bg: "var(--info-soft)",
    activeBg: "var(--info)",
    border: "var(--info)",
    activeBorder: "var(--info)",
    countColor: "var(--info)",
  },
]

export const TOO_EARLY_DEF = {
  key: "too_early" as Quadrant,
  emoji: "⏳",
  label: "Pantau Besok",
  action: "Tunggu data GSC",
  description:
    "Tempo sudah punya artikel untuk topik ini, tapi data Google Search Console-nya belum tersedia — artikel terlalu baru (GSC butuh 1–3 hari untuk mencerminkan performa). Cek besok untuk melihat apakah artikel mendapat trafik yang signifikan.",
  border: "var(--line)",
  activeBorder: "var(--accent)",
  countColor: "var(--fg-muted)",
}

export const QUADRANT_BY_KEY: Record<string, QuadrantDef | typeof TOO_EARLY_DEF> = {
  ...Object.fromEntries(QUADRANTS.map((q) => [q.key, q])),
  too_early: TOO_EARLY_DEF,
}
```

- [ ] **Step 2: Refactor `opportunity-matrix-card.tsx` to import from it**

In `frontend/packages/features/src/morning/opportunity-matrix-card.tsx`:

Delete the inline `type Quadrant` (line 11), the `interface QuadrantDef { ... }` (lines 13-26), the `const QUADRANTS: QuadrantDef[] = [ ... ]` (lines 28-86), and the `const TOO_EARLY_DEF = { ... }` (lines 88-98).

Add an import (next to the existing imports near the top):

```typescript
import { QUADRANTS, TOO_EARLY_DEF, type Quadrant, type QuadrantDef } from "./quadrants.js"
```

- [ ] **Step 3: Typecheck (refactor must not change types/behavior)**

```bash
cd frontend && bun run build
```
Expected: build succeeds. The matrix card compiles using the imported symbols.

- [ ] **Step 4: Run existing feature tests (sanity, no regression)**

```bash
cd frontend && bun test packages/features/tests/
```
Expected: PASS (volume-chart + sparkline + analyst-data tests unaffected).

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/features/src/morning/quadrants.ts \
        frontend/packages/features/src/morning/opportunity-matrix-card.tsx
git commit -m "refactor(fe): extract shared quadrant map to quadrants.ts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Frontend — `ClusterBentoCard` component + wire into `/morning`

**Files:**
- Create: `frontend/packages/features/src/morning/use-element-width.ts` (extract the existing hook for reuse)
- Modify: `frontend/packages/features/src/morning/news-volume-trend-card.tsx` (import the extracted hook)
- Create: `frontend/packages/features/src/morning/cluster-bento-card.tsx`
- Modify: `frontend/packages/features/src/morning/morning-view.tsx` (render the new card)

**Interfaces:**
- Consumes: `useClusterBento`, `useClusterVolumeTrend`, `BentoCard` (Task 3); `buildSparkline` (Task 4); `QUADRANT_BY_KEY` (Task 5); `VelocityBar`, `Button`, `Skeleton`, `ErrorState`, `EmptyState` (`@ei-fe/ui`).
- Produces: exported `ClusterBentoCard` React component (no props) rendered by `morning-view.tsx`.

This task has no pure-unit test (the repo unit-tests only pure functions/schemas; React components are verified by typecheck + manual). Verification = build passes + the manual checklist in Step 6.

- [ ] **Step 1: Extract `useElementWidth` into its own module**

Create `frontend/packages/features/src/morning/use-element-width.ts`:

```typescript
import { useLayoutEffect, useRef, useState } from "react"

export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setWidth(el.getBoundingClientRect().width)
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setWidth(e.contentRect.width)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}
```

In `frontend/packages/features/src/morning/news-volume-trend-card.tsx`, delete the local `useElementWidth` definition (lines 12-26) and add an import after line 5:

```typescript
import { useElementWidth } from "./use-element-width.js"
```

- [ ] **Step 2: Create the bento component**

Create `frontend/packages/features/src/morning/cluster-bento-card.tsx`:

```typescript
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useClusterBento, useClusterVolumeTrend, clusterKeys } from "@ei-fe/api"
import type { BentoCard as BentoCardData } from "@ei-fe/api"
import { useQueryClient } from "@tanstack/react-query"
import { Button, Skeleton, ErrorState, EmptyState, VelocityBar } from "@ei-fe/ui"
import { QUADRANT_BY_KEY } from "./quadrants.js"
import { useElementWidth } from "./use-element-width.js"
import { buildSparkline } from "./sparkline.js"

const PAGE = 8

const _relFmt = new Intl.RelativeTimeFormat("id-ID", { numeric: "auto" })

function relTime(iso: string | null): string {
  if (!iso) return "—"
  const then = new Date(/Z|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z").getTime()
  const diffMin = Math.round((then - Date.now()) / 60000)
  const absMin = Math.abs(diffMin)
  if (absMin < 60) return _relFmt.format(Math.round(diffMin), "minute")
  const diffHr = Math.round(diffMin / 60)
  if (Math.abs(diffHr) < 24) return _relFmt.format(diffHr, "hour")
  return _relFmt.format(Math.round(diffHr / 24), "day")
}

function fmtViews(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(".0", "") + "k"
  return String(n)
}

function quadrantStyle(key: string | null) {
  const def = (key && QUADRANT_BY_KEY[key]) || null
  return {
    label: def?.label ?? "Lainnya",
    bg: def?.bg ?? "var(--bg-sunken)",
    color: def?.countColor ?? "var(--fg-muted)",
  }
}

function Sparkline({ values }: { values: number[] }) {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const height = 48
  const model = width > 0 ? buildSparkline(values, { width, height, pad: 4 }) : null
  return (
    <div ref={ref} style={{ width: "100%" }}>
      {model && (
        <svg width="100%" height={height} role="img" aria-label="Tren volume kompetitor 48 jam">
          <path d={model.areaPath} fill="var(--accent-soft)" stroke="none" />
          <path d={model.linePath} fill="none" stroke="var(--accent)" strokeWidth={1.5} strokeLinejoin="round" />
          <circle cx={model.lastX} cy={model.lastY} r={2.4} fill="var(--accent)" />
        </svg>
      )}
    </div>
  )
}

function Stat({ k, v }: { k: string; v: string | number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "4px 0", fontSize: 12.5 }}>
      <span style={{ color: "var(--fg-muted)" }}>{k}</span>
      <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums", color: "var(--fg)" }}>{v}</span>
    </div>
  )
}

function BentoCard({ card }: { card: BentoCardData }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const q = quadrantStyle(card.editorial_quadrant)
  const series = useClusterVolumeTrend(card.id, open)
  const values = (series.data?.buckets ?? []).map((b) => b.competitor_count)

  return (
    <article
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onClick={() => setOpen((o) => !o)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          setOpen((o) => !o)
        }
      }}
      style={{
        gridColumn: open ? "span 2" : "span 1",
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        padding: "14px 15px",
        cursor: "pointer",
        boxShadow: open ? "var(--shadow-md)" : "var(--shadow-sm)",
        transition: "box-shadow .2s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span
          style={{
            fontSize: 10.5,
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            padding: "3px 9px",
            borderRadius: 999,
            background: q.bg,
            color: q.color,
          }}
        >
          {q.label}
        </span>
        <span style={{ color: "var(--fg-faint)", fontSize: 13, lineHeight: 1 }}>{open ? "－" : "＋"}</span>
      </div>

      <h3
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 16,
          lineHeight: 1.2,
          fontWeight: 600,
          margin: "10px 0 0",
          color: "var(--fg)",
          ...(open ? {} : { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", minHeight: "2.4em" }),
        }}
      >
        {card.label ?? "Belum dilabeli"}
      </h3>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
        <span style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)" }}>
          velocity
        </span>
        <div style={{ flex: 1 }}>
          <VelocityBar velocity={card.trend_velocity} max={3} />
        </div>
      </div>

      {open && (
        <div
          style={{
            marginTop: 14,
            paddingTop: 14,
            borderTop: "1px solid var(--line)",
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1.1fr",
            gap: 18,
          }}
        >
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)", marginBottom: 6 }}>
              Permintaan
            </div>
            <Stat k="Kompetitor" v={card.competitor_count ?? 0} />
            <Stat k="Trend" v={card.trend_match_count ?? 0} />
            <Stat k="Artikel" v={card.member_count ?? 0} />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)", marginBottom: 6 }}>
              Liputan kita
            </div>
            <Stat k="Artikel kita" v={card.internal_article_count} />
            <Stat k="Views" v={fmtViews(card.views)} />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
              <span>Kompetitor</span>
              <span style={{ color: "var(--fg-muted)" }}>48 jam</span>
            </div>
            {series.isLoading && <Skeleton className="w-full h-[48px]" />}
            {!series.isLoading && <Sparkline values={values} />}
            <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--fg-muted)", lineHeight: 1.5 }}>
              Kompetitor terakhir <b style={{ color: "var(--fg)" }}>{relTime(card.last_competitor_at)}</b>
              <br />
              Internal terakhir <b style={{ color: "var(--fg)" }}>{relTime(card.last_internal_at)}</b>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                navigate(`/clusters/${card.id}`)
              }}
              style={{
                marginTop: 10,
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--accent)",
                fontSize: 12.5,
                fontWeight: 600,
                padding: 0,
              }}
            >
              Buka klaster →
            </button>
          </div>
        </div>
      )}
    </article>
  )
}

export function ClusterBentoCard() {
  const [shown, setShown] = useState(PAGE)
  const qc = useQueryClient()
  const { data, isLoading, isError, error } = useClusterBento(shown)

  return (
    <div
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        padding: "18px 20px",
      }}
    >
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Klaster Topik</div>
        <div style={{ fontSize: 12, color: "var(--fg-muted)", marginTop: 2 }}>
          Status &amp; kecepatan tiap klaster — klik kartu untuk detail
        </div>
      </div>

      {isLoading && <Skeleton className="w-full h-[280px]" />}
      {isError && (
        <ErrorState
          error={error}
          onRetry={() => qc.invalidateQueries({ queryKey: clusterKeys.bento(shown) })}
        />
      )}
      {!isLoading && !isError && data && data.cards.length === 0 && (
        <EmptyState
          title="Belum ada klaster."
          description="Grid terisi setelah cluster run harian (06:00 WIB) selesai."
        />
      )}
      {!isLoading && !isError && data && data.cards.length > 0 && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 14,
              alignItems: "start",
            }}
          >
            {data.cards.map((c) => (
              <BentoCard key={c.id} card={c} />
            ))}
          </div>
          {data.cards.length < data.total && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 18 }}>
              <Button variant="outline" size="md" onClick={() => setShown((s) => s + PAGE)}>
                Tampilkan {Math.min(PAGE, data.total - data.cards.length)} lagi · {data.cards.length} dari {data.total}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire it into the morning view**

In `frontend/packages/features/src/morning/morning-view.tsx`:

Add an import after line 10 (`import { NewsVolumeTrendCard } ...`):

```typescript
import { ClusterBentoCard } from "./cluster-bento-card.js"
```

Insert the card after the `NewsVolumeTrendCard` block (after line 109, before the force-graph `<div>`):

```typescript
      <div style={{ padding: "20px 28px 0" }}>
        <ClusterBentoCard />
      </div>
```

- [ ] **Step 4: Typecheck / build**

```bash
cd frontend && bun run build
```
Expected: build succeeds (no type errors).

- [ ] **Step 5: Run the full frontend test suite (no regressions)**

```bash
cd frontend && bun test
```
Expected: PASS.

- [ ] **Step 6: Manual verification**

Prereq: backend running with scored data. From `backend/`: `docker compose up -d` then ensure a scored run exists. Start the frontend: `cd frontend && bun run dev`. Open `/morning` and confirm:
  - A "Klaster Topik" card appears after "Volume Berita", showing a 4-column grid of compact cards (status chip + serif label + velocity).
  - Clicking a card expands it (spans 2 columns) and reveals Permintaan / Liputan kita stats, the 48-jam competitor sparkline (network tab shows a `GET /clusters/{id}/volume-trend?bucket=hour` firing only on first expand), and the two timestamps.
  - Opening a second card collapses the first (single-open).
  - "Buka klaster →" navigates to `/clusters/{id}` without toggling.
  - Keyboard: Tab to a card, Enter/Space toggles it.
  - "Tampilkan 8 lagi" reveals 8 more and disappears once all `total` cards are shown.

- [ ] **Step 7: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/features/src/morning/use-element-width.ts \
        frontend/packages/features/src/morning/news-volume-trend-card.tsx \
        frontend/packages/features/src/morning/cluster-bento-card.tsx \
        frontend/packages/features/src/morning/morning-view.tsx
git commit -m "feat(fe): cluster bento card with click-to-expand + lazy sparkline on /morning

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Tier 1 / 2 / 3 + click-to-expand → Task 6 (`BentoCard`). ✅
- 4×2 grid + "Show more (+8)" pagination → Task 6 (`ClusterBentoCard`, `PAGE=8`, grid `repeat(4,1fr)`). ✅
- Lazy per-card sparkline → Task 2 (endpoint) + Task 3 (`useClusterVolumeTrend(id, enabled=open)`) + Task 6. ✅
- `/clusters/bento` ranked across all quadrants, paginated, `total` → Task 1. ✅
- Shared ranking helper (no drift) → Task 1 (`_ranking_order()`, morning refactored). ✅
- On-read enrichment, no migration → Task 1 (grouped FILTER query). ✅
- `views` = `gsc_clicks`, scoped D35 reversal + docs + leak test → Task 1 (steps 9-12). ✅
- Design-system mapping (tokens, `QUADRANT_BY_KEY`, `VelocityBar`, `--font-serif`, `volume-chart`/`useElementWidth` patterns, `Button`) → Tasks 4-6. ✅
- "Buka klaster →" navigation disambiguated from expand → Task 6 (`stopPropagation`). ✅
- Tests: ranking parity, pagination, views, enrichment, leak; per-cluster bucketing/404; FE schema + sparkline → Tasks 1-4. ✅

**Placeholder scan:** No TBD/TODO; every code/test step contains complete content. ✅

**Type consistency:** `BentoCard`/`BentoListResponse` field names match between the Pydantic models (Task 1), the Zod schemas (Task 3), and component usage (Task 6: `card.views`, `card.internal_article_count`, `card.last_competitor_at`, `card.last_internal_at`, `card.editorial_quadrant`, `card.trend_velocity`). `buildSparkline` signature matches between Task 4 (def) and Task 6 (call: `{ width, height, pad }`). `useClusterBento(limit)` / `useClusterVolumeTrend(id, enabled)` signatures match between Task 3 (def) and Task 6 (call). `QUADRANT_BY_KEY` shape matches between Task 5 (def) and Task 6 (`.label`/`.bg`/`.countColor`). ✅
