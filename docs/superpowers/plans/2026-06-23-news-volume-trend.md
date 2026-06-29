# News Volume Trend chart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stacked bar chart to the Morning Brief showing news volume over time (competitor RSS + internal Tempo), with an hourly/daily x-axis toggle and hover tooltips, so editors can spot spikes.

**Architecture:** A new read-only FastAPI endpoint `GET /api/v1/articles/volume-trend` returns a dense, zero-filled time series of article counts bucketed by WIB hour or day and split by source type. A self-contained Morning Brief card fetches it via a TanStack Query hook (Zod-validated) and renders a stacked SVG bar chart built with React + `d3-scale`. Chart geometry and label formatting live in a pure, unit-tested helper module.

**Tech Stack:** FastAPI, SQLAlchemy (async), Postgres (`date_trunc`, `timezone()`), Pydantic. Frontend: React, TanStack Query, Zod, `d3` (already a dependency — `scaleBand`/`scaleLinear`), Tailwind + CSS-variable design tokens, `bun test`.

## Global Constraints

- **No new dependency.** `d3@^7.9.0` is already in `frontend/packages/features/package.json`; import `scaleBand`/`scaleLinear` from `"d3"`. Do NOT add recharts or anything else. No `docs/tech-stack.md` change.
- **No DB schema change / no migration.** The endpoint only reads existing `article` + `content_source` columns.
- **`api` never imports ML modules.** This is a plain SQL read endpoint — fine.
- **GSC rule:** article counts/timestamps are NOT GSC metrics and are freely returnable. Do not touch `article_gsc_metric` or `cluster_insight` GSC columns.
- **Wire datetime format:** ISO-8601 UTC with `Z` suffix via `api.types.UtcDateTime` (the serializer tags naive datetimes as UTC).
- **Endpoint change rule:** the same commit adds the Pydantic response model, `response_model=`, status code (200 default), and a one-line `summary=`.
- **Frontend layering:** new component lives in `features/morning`, imports shared UI only from `@ei-fe/ui` and data only from `@ei-fe/api`. NO legacy global CSS classes (`.card`, `.kw-row`) — Tailwind utilities + inline styles referencing CSS-var tokens only.
- **Timezone:** WIB is a fixed UTC+7 (no DST). All bucketing is in WIB so days/hours align to the editorial clock.
- **Branch:** all work on a fresh branch off `master` (the current `feat/ai-analyst-frontend` branch is unrelated).

---

## File Structure

**Backend**
- Modify `backend/packages/api/src/api/routes/articles.py` — add `VolumeBucket`, `VolumeTrendResponse`, the `_dense_bucket_starts` helper, and the `volume_trend` route.
- Create `backend/packages/api/tests/test_volume_trend.py` — integration tests via the ASGI client.

**Frontend — data layer (`@ei-fe/api`)**
- Modify `frontend/packages/api/src/keys.ts` — add `articleKeys.volumeTrend`.
- Modify `frontend/packages/api/src/schemas.ts` — add `VolumeBucketSchema`, `VolumeTrendResponseSchema` + inferred types.
- Modify `frontend/packages/api/src/queries.ts` — add `useVolumeTrend` hook.
- Modify `frontend/packages/api/src/index.ts` — export the hook, types, and schemas.
- Regenerate `frontend/packages/api/src/generated.ts` (codegen; needs API running).

**Frontend — feature (`@ei-fe/features`)**
- Create `frontend/packages/features/src/morning/volume-chart.ts` — pure helpers: `buildVolumeChart`, `formatBucketLabel`, `formatBucketTooltip` (+ `Bar`, `ChartDims`, `ChartModel` types).
- Create `frontend/packages/features/tests/volume-chart.test.ts` — `bun test` for the pure helpers.
- Create `frontend/packages/features/src/morning/news-volume-trend-card.tsx` — the card component.
- Modify `frontend/packages/features/src/morning/morning-view.tsx` — render the card after `OpportunityMatrixCard`.

**Docs**
- Modify `CLAUDE.md` — add the endpoint to the "Live read endpoints" list.

---

## Setup (before Task 1)

- [ ] **Create the working branch off `master`** (or an isolated worktree via the using-git-worktrees skill).

```bash
cd /home/shendi/self-project/content-intelligence
git fetch origin
git switch -c feat/news-volume-trend origin/master
```

If you cannot branch off a clean `master` (dirty tree from the current branch), use a git worktree instead so this work is isolated.

---

## Task 1: Backend `GET /api/v1/articles/volume-trend`

**Files:**
- Modify: `backend/packages/api/src/api/routes/articles.py`
- Test: `backend/packages/api/tests/test_volume_trend.py`

**Interfaces:**
- Produces (consumed by Task 2's Zod schema): JSON
  `{ bucket: "hour"|"day", buckets: [{ bucket_start: <ISO Z>, competitor_count: int, internal_count: int }], generated_at: <ISO Z> }`.
  `bucket_start` is the UTC instant of each WIB bucket start; series is dense (48 hourly / 30 daily buckets) and zero-filled; ascending by `bucket_start`.

- [ ] **Step 1: Write the failing tests**

Create `backend/packages/api/tests/test_volume_trend.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta, timezone

from core.models import Article, ContentSource, SourceType
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_WIB = timezone(timedelta(hours=7))
_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType = SourceType.rss, *, name: str = "Vol Source") -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name=name,
        url=f"https://test-{uuid.uuid4()}.com/rss",
        source_type=source_type,
    )


def _article(
    source_id: uuid.UUID,
    *,
    published_at: datetime | None = None,
    created_at: datetime | None = None,
    title: str = "Vol Article",
) -> Article:
    a = Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title=title,
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )
    if created_at is not None:
        a.created_at = created_at
    return a


def _wib_day_bucket_utc_iso(ts_naive_utc: datetime) -> str:
    """UTC instant (Z-suffixed) of the WIB-day bucket that contains ts."""
    wib = ts_naive_utc.replace(tzinfo=UTC).astimezone(_WIB)
    wib_mid = wib.replace(hour=0, minute=0, second=0, microsecond=0)
    return wib_mid.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def test_volume_trend_response_shape(client: AsyncClient) -> None:
    r = await client.get("/api/v1/articles/volume-trend")
    assert r.status_code == 200
    d = r.json()
    assert d["bucket"] == "day"
    assert isinstance(d["buckets"], list)
    assert "generated_at" in d
    b = d["buckets"][0]
    assert set(b.keys()) == {"bucket_start", "competitor_count", "internal_count"}


async def test_volume_trend_day_has_30_dense_buckets(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    assert len(d["buckets"]) == 30


async def test_volume_trend_hour_has_48_dense_buckets(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=hour")).json()
    assert d["bucket"] == "hour"
    assert len(d["buckets"]) == 48


async def test_volume_trend_invalid_bucket_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/articles/volume-trend?bucket=week")
    assert r.status_code == 422


async def test_volume_trend_empty_db_all_zero(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    assert len(d["buckets"]) == 30
    assert all(b["competitor_count"] == 0 and b["internal_count"] == 0 for b in d["buckets"])


async def test_volume_trend_splits_competitor_and_internal(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss, name="Kompas")
    internal = _source(SourceType.internal, name="Tempo")
    ts = _NOW - timedelta(hours=3)
    session.add_all(
        [rss, internal, _article(rss.id, published_at=ts), _article(internal.id, published_at=ts)]
    )
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    by_start = {b["bucket_start"]: b for b in d["buckets"]}
    target = _wib_day_bucket_utc_iso(ts)
    assert by_start[target]["competitor_count"] == 1
    assert by_start[target]["internal_count"] == 1


async def test_volume_trend_buckets_by_wib_day_not_utc(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss)
    # 18:00 UTC → 01:00 WIB next day → belongs to the *next* WIB day's bucket.
    ts = (_NOW - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    session.add_all([rss, _article(rss.id, published_at=ts)])
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    by_start = {b["bucket_start"]: b for b in d["buckets"]}
    target = _wib_day_bucket_utc_iso(ts)
    # Counted exactly once, in the WIB-day bucket.
    assert sum(b["competitor_count"] for b in d["buckets"]) == 1
    assert by_start[target]["competitor_count"] == 1


async def test_volume_trend_uses_created_at_when_published_null(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss)
    ts = _NOW - timedelta(hours=5)
    session.add_all([rss, _article(rss.id, published_at=None, created_at=ts)])
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    by_start = {b["bucket_start"]: b for b in d["buckets"]}
    target = _wib_day_bucket_utc_iso(ts)
    assert by_start[target]["competitor_count"] == 1


async def test_volume_trend_excludes_articles_older_than_window(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss)
    session.add_all([rss, _article(rss.id, published_at=_NOW - timedelta(days=40))])
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    assert sum(b["competitor_count"] for b in d["buckets"]) == 0


async def test_volume_trend_bucket_starts_sorted_unique_utc(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    starts = [b["bucket_start"] for b in d["buckets"]]
    assert all(s.endswith("Z") for s in starts)
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/shendi/self-project/content-intelligence/backend
docker compose up -d postgres
docker compose run --rm api pytest packages/api/tests/test_volume_trend.py -v
```

Expected: FAIL — `volume-trend` returns 404 (route not defined), so most assertions error.

- [ ] **Step 3: Implement the endpoint**

In `backend/packages/api/src/api/routes/articles.py`, extend the imports and add the models + route.

Change the top imports to include the datetime/typing/enum needs:

```python
import math
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

from core.models import Article, ContentSource, SourceType
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import SessionDep
from api.types import UtcDateTime
```

Append after `PaginatedArticles` (module level):

```python
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


def _dense_bucket_starts(bucket: Literal["hour", "day"], now_utc: datetime) -> list[datetime]:
    """Naive WIB wall-clock bucket starts, oldest→newest, covering the range."""
    step, count = _RANGE[bucket]
    now_wib = now_utc.astimezone(_WIB).replace(tzinfo=None)
    if bucket == "hour":
        current = now_wib.replace(minute=0, second=0, microsecond=0)
    else:
        current = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    return [current - step * i for i in range(count - 1, -1, -1)]
```

Append the route after `list_articles`:

```python
@router.get(
    "/volume-trend",
    response_model=VolumeTrendResponse,
    summary="Article volume per WIB time bucket, split by source type",
)
async def volume_trend(
    session: SessionDep,
    bucket: Literal["hour", "day"] = Query("day"),
) -> VolumeTrendResponse:
    now_utc = datetime.now(UTC)
    starts_wib = _dense_bucket_starts(bucket, now_utc)
    cutoff_utc = starts_wib[0] - timedelta(hours=7)  # naive UTC lower bound

    effective = func.coalesce(Article.published_at, Article.created_at)
    wib_local = func.timezone("Asia/Jakarta", func.timezone("UTC", effective))
    wib_bucket = func.date_trunc(bucket, wib_local)

    stmt = (
        select(
            wib_bucket.label("wib_bucket"),
            ContentSource.source_type.label("source_type"),
            func.count(Article.id).label("cnt"),
        )
        .join(ContentSource, ContentSource.id == Article.source_id)
        .where(effective >= cutoff_utc)
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

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/shendi/self-project/content-intelligence/backend
docker compose run --rm api pytest packages/api/tests/test_volume_trend.py -v
```

Expected: PASS (all tests). If `_wib_day_bucket_utc_iso` lookups `KeyError`, the WIB conversion in `wib_local` is wrong — recheck the `timezone("Asia/Jakarta", timezone("UTC", ...))` order.

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/api/src/api/routes/articles.py backend/packages/api/tests/test_volume_trend.py
git commit -m "feat(api): add /articles/volume-trend endpoint (WIB-bucketed, source-split)"
```

---

## Task 2: Frontend data layer (`@ei-fe/api`)

**Files:**
- Modify: `frontend/packages/api/src/keys.ts`
- Modify: `frontend/packages/api/src/schemas.ts`
- Modify: `frontend/packages/api/src/queries.ts`
- Modify: `frontend/packages/api/src/index.ts`
- Regenerate: `frontend/packages/api/src/generated.ts`

**Interfaces:**
- Consumes (from Task 1): the `/articles/volume-trend` JSON shape.
- Produces (consumed by Tasks 3 & 4): `useVolumeTrend(bucket)` hook; `VolumeBucket`, `VolumeTrendResponse` types; `articleKeys.volumeTrend(bucket)`.

- [ ] **Step 1: Add the query key**

In `frontend/packages/api/src/keys.ts`, replace the `articleKeys` block:

```ts
export const articleKeys = {
  all: ["articles"] as const,
  list: (page: number, pageSize: number) => [...articleKeys.all, "list", page, pageSize] as const,
  volumeTrend: (bucket: "hour" | "day") => [...articleKeys.all, "volume-trend", bucket] as const,
}
```

- [ ] **Step 2: Add the Zod schemas**

In `frontend/packages/api/src/schemas.ts`, add after the `PaginatedArticlesSchema` block:

```ts
export const VolumeBucketSchema = z.object({
  bucket_start: z.string(),
  competitor_count: z.number().int(),
  internal_count: z.number().int(),
})
export type VolumeBucket = z.infer<typeof VolumeBucketSchema>

export const VolumeTrendResponseSchema = z.object({
  bucket: z.enum(["hour", "day"]),
  buckets: z.array(VolumeBucketSchema),
  generated_at: z.string(),
})
export type VolumeTrendResponse = z.infer<typeof VolumeTrendResponseSchema>
```

- [ ] **Step 3: Add the hook**

In `frontend/packages/api/src/queries.ts`, add `VolumeTrendResponseSchema` to the existing `from "./schemas.js"` import, then add:

```ts
export function useVolumeTrend(bucket: "hour" | "day") {
  return useQuery({
    queryKey: articleKeys.volumeTrend(bucket),
    queryFn: () => apiGet(`/articles/volume-trend?bucket=${bucket}`, VolumeTrendResponseSchema),
    staleTime: 5 * 60 * 1000,
  })
}
```

- [ ] **Step 4: Export from the package index**

In `frontend/packages/api/src/index.ts`:
- add `useVolumeTrend` to the `from "./queries.js"` export list,
- add `VolumeBucket, VolumeTrendResponse` to the `export type { ... } from "./schemas.js"` list,
- add `VolumeBucketSchema, VolumeTrendResponseSchema` to the schema-value `export { ... } from "./schemas.js"` list.

- [ ] **Step 5: Type-check the data layer**

```bash
cd /home/shendi/self-project/content-intelligence/frontend
bun run --filter @ei-fe/api lint || npx tsc -p packages/api --noEmit
```

Expected: no type errors referencing the new symbols. (If the package has no standalone typecheck, the app build in Task 5 covers it.)

- [ ] **Step 6: Regenerate the OpenAPI types**

Requires the API running (from Task 1, `docker compose up -d` in `backend/`, reachable at `http://localhost:8000`).

```bash
cd /home/shendi/self-project/content-intelligence/frontend
bun run gen:api
```

If `localhost:8000` is not reachable, this step may be skipped — runtime types come from the Zod schema in Step 2; note the skip in the commit message. (`generated.ts` is a committed mirror, not imported by the hooks.)

- [ ] **Step 7: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/api/src/keys.ts frontend/packages/api/src/schemas.ts frontend/packages/api/src/queries.ts frontend/packages/api/src/index.ts frontend/packages/api/src/generated.ts
git commit -m "feat(fe-api): useVolumeTrend hook + volume-trend schema/keys"
```

---

## Task 3: Pure chart helper + tests (`volume-chart.ts`)

**Files:**
- Create: `frontend/packages/features/src/morning/volume-chart.ts`
- Test: `frontend/packages/features/tests/volume-chart.test.ts`

**Interfaces:**
- Consumes (from Task 2): `VolumeBucket` type.
- Produces (consumed by Task 4): `buildVolumeChart(buckets, dims): ChartModel`, `formatBucketLabel(iso, bucket): string`, `formatBucketTooltip(iso): string`, and the `Bar` / `ChartDims` / `ChartModel` types.

- [ ] **Step 1: Write the failing tests**

Create `frontend/packages/features/tests/volume-chart.test.ts`:

```ts
import { describe, test, expect } from "bun:test"
import { buildVolumeChart, formatBucketLabel, formatBucketTooltip } from "../src/morning/volume-chart.js"

const DIMS = { width: 600, height: 200, padTop: 10, padRight: 10, padBottom: 30, padLeft: 30 }

function bkt(bucket_start: string, c: number, i: number) {
  return { bucket_start, competitor_count: c, internal_count: i }
}

describe("buildVolumeChart", () => {
  test("one bar per bucket", () => {
    const m = buildVolumeChart([bkt("2026-06-22T17:00:00Z", 1, 2), bkt("2026-06-23T17:00:00Z", 0, 0)], DIMS)
    expect(m.bars).toHaveLength(2)
  })

  test("maxTotal is the largest stacked total", () => {
    const m = buildVolumeChart([bkt("a", 1, 1), bkt("b", 3, 2)], DIMS)
    expect(m.maxTotal).toBe(5)
  })

  test("tallest bar fills inner height; segments sum to it", () => {
    const m = buildVolumeChart([bkt("a", 2, 2)], DIMS) // total 4 == max
    const bar = m.bars[0]
    expect(bar.competitorH + bar.internalH).toBeCloseTo(m.innerHeight, 5)
  })

  test("internal stacks directly on top of competitor", () => {
    const m = buildVolumeChart([bkt("a", 3, 1)], DIMS)
    const bar = m.bars[0]
    expect(bar.internalY + bar.internalH).toBeCloseTo(bar.competitorY, 5)
  })

  test("a bar with double the total is twice as tall", () => {
    const m = buildVolumeChart([bkt("a", 1, 0), bkt("b", 2, 0)], DIMS)
    expect(m.bars[1].competitorH).toBeCloseTo(2 * m.bars[0].competitorH, 5)
  })

  test("all-zero buckets yield zero-height bars, no NaN", () => {
    const m = buildVolumeChart([bkt("a", 0, 0), bkt("b", 0, 0)], DIMS)
    for (const bar of m.bars) {
      expect(bar.competitorH).toBe(0)
      expect(bar.internalH).toBe(0)
      expect(Number.isNaN(bar.x)).toBe(false)
    }
  })

  test("bars run left→right inside the plot area", () => {
    const m = buildVolumeChart([bkt("a", 1, 0), bkt("b", 1, 0), bkt("c", 1, 0)], DIMS)
    expect(m.bars[0].x).toBeGreaterThanOrEqual(DIMS.padLeft)
    expect(m.bars[0].x).toBeLessThan(m.bars[1].x)
    expect(m.bars[2].x + m.bars[2].width).toBeLessThanOrEqual(DIMS.width - DIMS.padRight + 0.001)
  })
})

describe("formatBucketLabel", () => {
  test("day label is WIB day + Indonesian short month", () => {
    // 2026-06-11T17:00:00Z == 2026-06-12 00:00 WIB
    expect(formatBucketLabel("2026-06-11T17:00:00Z", "day")).toBe("12 Jun")
  })

  test("hour label is WIB 24h time", () => {
    // 2026-06-12T07:00:00Z == 2026-06-12 14:00 WIB
    expect(formatBucketLabel("2026-06-12T07:00:00Z", "hour")).toMatch(/^14[.:]00$/)
  })
})

describe("formatBucketTooltip", () => {
  test("includes the WIB suffix", () => {
    expect(formatBucketTooltip("2026-06-12T07:00:00Z")).toContain("WIB")
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/shendi/self-project/content-intelligence/frontend
bun test packages/features/tests/volume-chart.test.ts
```

Expected: FAIL — cannot resolve `../src/morning/volume-chart.js` (module not created).

- [ ] **Step 3: Implement the helper**

Create `frontend/packages/features/src/morning/volume-chart.ts`:

```ts
import { scaleBand, scaleLinear } from "d3"
import type { VolumeBucket } from "@ei-fe/api"

export interface ChartDims {
  width: number
  height: number
  padTop: number
  padRight: number
  padBottom: number
  padLeft: number
}

export interface Bar {
  index: number
  x: number
  width: number
  competitorY: number
  competitorH: number
  internalY: number
  internalH: number
  total: number
  bucket: VolumeBucket
}

export interface ChartModel {
  bars: Bar[]
  maxTotal: number
  innerWidth: number
  innerHeight: number
}

export function buildVolumeChart(buckets: VolumeBucket[], dims: ChartDims): ChartModel {
  const innerWidth = Math.max(0, dims.width - dims.padLeft - dims.padRight)
  const innerHeight = Math.max(0, dims.height - dims.padTop - dims.padBottom)
  const maxTotal = buckets.reduce(
    (m, b) => Math.max(m, b.competitor_count + b.internal_count),
    0,
  )

  const x = scaleBand<number>()
    .domain(buckets.map((_, i) => i))
    .range([0, innerWidth])
    .paddingInner(0.2)
    .paddingOuter(0.1)
  const y = scaleLinear().domain([0, maxTotal || 1]).range([innerHeight, 0])

  const bars: Bar[] = buckets.map((bucket, index) => {
    const competitorH = innerHeight - y(bucket.competitor_count)
    const internalH = innerHeight - y(bucket.internal_count)
    const competitorY = dims.padTop + innerHeight - competitorH
    const internalY = competitorY - internalH
    return {
      index,
      x: dims.padLeft + (x(index) ?? 0),
      width: x.bandwidth(),
      competitorY,
      competitorH,
      internalY,
      internalH,
      total: bucket.competitor_count + bucket.internal_count,
      bucket,
    }
  })

  return { bars, maxTotal, innerWidth, innerHeight }
}

const _dayFmt = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  timeZone: "Asia/Jakarta",
})
const _hourFmt = new Intl.DateTimeFormat("id-ID", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Asia/Jakarta",
})
const _tooltipFmt = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Asia/Jakarta",
})

export function formatBucketLabel(iso: string, bucket: "hour" | "day"): string {
  const d = new Date(iso)
  return bucket === "day" ? _dayFmt.format(d) : _hourFmt.format(d)
}

export function formatBucketTooltip(iso: string): string {
  return `${_tooltipFmt.format(new Date(iso))} WIB`
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/shendi/self-project/content-intelligence/frontend
bun test packages/features/tests/volume-chart.test.ts
```

Expected: PASS. If the `day` label assertion fails, check the runtime's `id-ID` short-month output (June → `Jun`); adjust the expectation only if the runtime genuinely differs.

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/features/src/morning/volume-chart.ts frontend/packages/features/tests/volume-chart.test.ts
git commit -m "feat(morning): pure volume-chart geometry + WIB label helpers"
```

---

## Task 4: `NewsVolumeTrendCard` component

**Files:**
- Create: `frontend/packages/features/src/morning/news-volume-trend-card.tsx`

**Interfaces:**
- Consumes: `useVolumeTrend`, `articleKeys` (Task 2); `buildVolumeChart`, `formatBucketLabel`, `formatBucketTooltip`, `Bar` (Task 3); `Skeleton`, `ErrorState`, `EmptyState` from `@ei-fe/ui`.
- Produces (consumed by Task 5): `export function NewsVolumeTrendCard()`.

- [ ] **Step 1: Implement the component**

Create `frontend/packages/features/src/morning/news-volume-trend-card.tsx`:

```tsx
import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useVolumeTrend, articleKeys } from "@ei-fe/api"
import { Skeleton, ErrorState, EmptyState } from "@ei-fe/ui"
import { buildVolumeChart, formatBucketLabel, formatBucketTooltip, type Bar } from "./volume-chart.js"

const HEIGHT = 260
const PAD = { padTop: 12, padRight: 14, padBottom: 28, padLeft: 36 }
const COMPETITOR_COLOR = "var(--fg-faint)"
const INTERNAL_COLOR = "var(--accent)"

function useElementWidth<T extends HTMLElement>() {
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

function LegendDot({ color }: { color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 9,
        height: 9,
        borderRadius: 2,
        background: color,
        marginRight: 5,
        verticalAlign: "middle",
      }}
    />
  )
}

function Toggle({
  bucket,
  onChange,
}: {
  bucket: "hour" | "day"
  onChange: (b: "hour" | "day") => void
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 3,
        background: "var(--bg-sunken)",
        padding: 3,
        borderRadius: "var(--radius)",
      }}
    >
      {(["hour", "day"] as const).map((b) => (
        <button
          key={b}
          type="button"
          aria-pressed={bucket === b}
          onClick={() => onChange(b)}
          style={{
            border: "none",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 500,
            padding: "4px 14px",
            borderRadius: 4,
            background: bucket === b ? "var(--bg-elev)" : "transparent",
            color: bucket === b ? "var(--fg)" : "var(--fg-muted)",
            boxShadow: bucket === b ? "var(--shadow-sm)" : "none",
          }}
        >
          {b === "hour" ? "Jam" : "Hari"}
        </button>
      ))}
    </div>
  )
}

function Tooltip({ bar, bucket }: { bar: Bar; bucket: "hour" | "day" }) {
  return (
    <div
      style={{
        position: "absolute",
        left: bar.x + bar.width / 2,
        top: bar.internalY,
        transform: "translate(-50%, calc(-100% - 8px))",
        background: "var(--fg)",
        color: "var(--bg-elev)",
        padding: "6px 10px",
        borderRadius: 6,
        fontSize: 11.5,
        lineHeight: 1.55,
        whiteSpace: "nowrap",
        pointerEvents: "none",
        boxShadow: "var(--shadow-md)",
        zIndex: 10,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 2 }}>
        {formatBucketTooltip(bar.bucket.bucket_start)}
      </div>
      <div>
        <LegendDot color={INTERNAL_COLOR} />
        Internal: {bar.bucket.internal_count}
      </div>
      <div>
        <LegendDot color={COMPETITOR_COLOR} />
        Kompetitor: {bar.bucket.competitor_count}
      </div>
      <div style={{ marginTop: 2, opacity: 0.85 }}>Total: {bar.total}</div>
    </div>
  )
}

function Chart({
  width,
  bucket,
  buckets,
}: {
  width: number
  bucket: "hour" | "day"
  buckets: { bucket_start: string; competitor_count: number; internal_count: number }[]
}) {
  const [hover, setHover] = useState<number | null>(null)
  const model = buildVolumeChart(buckets, { width, height: HEIGHT, ...PAD })
  const { bars, maxTotal, innerHeight, innerWidth } = model
  const labelEvery = Math.max(1, Math.ceil(bars.length / 10))
  const yTicks = Array.from(new Set([0, Math.round(maxTotal / 2), maxTotal]))
  const plotRight = PAD.padLeft + innerWidth

  return (
    <div style={{ position: "relative", height: HEIGHT }}>
      <svg width="100%" height={HEIGHT} role="img" aria-label="Grafik volume berita kompetitor dan internal">
        {yTicks.map((t) => {
          const yPix = PAD.padTop + innerHeight - (maxTotal ? (innerHeight * t) / maxTotal : 0)
          return (
            <g key={t}>
              <line
                x1={PAD.padLeft}
                x2={plotRight}
                y1={yPix}
                y2={yPix}
                stroke="var(--line)"
                strokeDasharray="2 3"
              />
              <text x={PAD.padLeft - 8} y={yPix + 3} textAnchor="end" fontSize={10} fill="var(--fg-faint)">
                {t}
              </text>
            </g>
          )
        })}

        {bars.map((bar) => {
          const active = hover === null || hover === bar.index
          return (
            <g
              key={bar.index}
              onMouseEnter={() => setHover(bar.index)}
              onMouseLeave={() => setHover((h) => (h === bar.index ? null : h))}
            >
              <rect x={bar.x} y={PAD.padTop} width={bar.width} height={innerHeight} fill="transparent" />
              <rect
                x={bar.x}
                y={bar.competitorY}
                width={bar.width}
                height={bar.competitorH}
                fill={COMPETITOR_COLOR}
                rx={1}
                opacity={active ? 1 : 0.45}
              />
              <rect
                x={bar.x}
                y={bar.internalY}
                width={bar.width}
                height={bar.internalH}
                fill={INTERNAL_COLOR}
                rx={1}
                opacity={active ? 1 : 0.45}
              />
            </g>
          )
        })}

        {bars.map((bar) =>
          bar.index % labelEvery === 0 ? (
            <text
              key={bar.index}
              x={bar.x + bar.width / 2}
              y={HEIGHT - 8}
              textAnchor="middle"
              fontSize={10}
              fill="var(--fg-faint)"
            >
              {formatBucketLabel(bar.bucket.bucket_start, bucket)}
            </text>
          ) : null,
        )}
      </svg>

      {hover !== null && bars[hover] && <Tooltip bar={bars[hover]} bucket={bucket} />}
    </div>
  )
}

export function NewsVolumeTrendCard() {
  const [bucket, setBucket] = useState<"hour" | "day">("day")
  const qc = useQueryClient()
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const { data, isLoading, isError, error } = useVolumeTrend(bucket)

  const isEmpty =
    data != null && data.buckets.every((b) => b.competitor_count + b.internal_count === 0)

  return (
    <div
      ref={ref}
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        padding: "18px 20px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 10,
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Volume Berita</div>
          <div style={{ fontSize: 12, color: "var(--fg-muted)", marginTop: 2 }}>
            Kompetitor &amp; internal — lonjakan berita dari waktu ke waktu
          </div>
        </div>
        <Toggle bucket={bucket} onChange={setBucket} />
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: 11.5, color: "var(--fg-muted)" }}>
        <span>
          <LegendDot color={INTERNAL_COLOR} />
          Internal (Tempo)
        </span>
        <span>
          <LegendDot color={COMPETITOR_COLOR} />
          Kompetitor (RSS)
        </span>
      </div>

      {isLoading && <Skeleton className="w-full" style={{ height: HEIGHT }} />}
      {isError && (
        <ErrorState
          error={error}
          onRetry={() => qc.invalidateQueries({ queryKey: articleKeys.volumeTrend(bucket) })}
        />
      )}
      {!isLoading && !isError && isEmpty && (
        <EmptyState
          title="Belum ada data volume berita."
          description="Grafik terisi setelah artikel masuk pada rentang waktu ini."
        />
      )}
      {!isLoading && !isError && data && !isEmpty && width > 0 && (
        <Chart width={width} bucket={bucket} buckets={data.buckets} />
      )}
    </div>
  )
}
```

> Note: `Skeleton` accepts `className`; if it rejects the inline `style` prop on typecheck, replace with `<Skeleton className="w-full h-[260px]" />`.

- [ ] **Step 2: Type-check / build the component**

```bash
cd /home/shendi/self-project/content-intelligence/frontend
bun run build
```

Expected: build succeeds (this compiles `@ei-fe/features` through the app). Fix any type errors before continuing.

- [ ] **Step 3: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/features/src/morning/news-volume-trend-card.tsx
git commit -m "feat(morning): NewsVolumeTrendCard stacked SVG chart with toggle + tooltip"
```

---

## Task 5: Wire card into Morning Brief + manual verification

**Files:**
- Modify: `frontend/packages/features/src/morning/morning-view.tsx`

**Interfaces:**
- Consumes: `NewsVolumeTrendCard` (Task 4).

- [ ] **Step 1: Import and render the card**

In `frontend/packages/features/src/morning/morning-view.tsx`:

Add the import alongside the other card imports:

```tsx
import { NewsVolumeTrendCard } from "./news-volume-trend-card.js"
```

Insert the card between the `OpportunityMatrixCard` wrapper and the `ClusterForceGraph` wrapper:

```tsx
      <div style={{ padding: "20px 28px 0" }}>
        <OpportunityMatrixCard clusters={clusters} />
      </div>

      <div style={{ padding: "20px 28px 0" }}>
        <NewsVolumeTrendCard />
      </div>

      <div style={{ padding: "20px 28px 0" }}>
        <ClusterForceGraph
```

- [ ] **Step 2: Run the full frontend test + build**

```bash
cd /home/shendi/self-project/content-intelligence/frontend
bun test
bun run build
```

Expected: all tests pass; build succeeds.

- [ ] **Step 3: Manual verification in the running app**

Start the backend stack and the frontend dev server, then inspect the Morning Brief.

```bash
cd /home/shendi/self-project/content-intelligence/backend
docker compose up -d
# in a second shell:
cd /home/shendi/self-project/content-intelligence/frontend
bun run dev
```

Confirm by observation (use the Playwright MCP browser tools or a manual browser at the dev URL, Morning Brief route):
- The "Volume Berita" card renders between the opportunity matrix and the force graph.
- Bars are stacked (internal accent on top of competitor slate); a recent spike is visible if data exists.
- The **Jam / Hari** toggle switches the x-axis; labels read in WIB (`14.00` for Jam, `12 Jun` for Hari).
- Hovering a bar shows a tooltip with WIB time + Internal / Kompetitor / Total counts; non-hovered bars dim.
- With an empty range, the empty state shows instead of a blank chart.

Capture a screenshot for the PR if using Playwright.

- [ ] **Step 4: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add frontend/packages/features/src/morning/morning-view.tsx
git commit -m "feat(morning): place NewsVolumeTrendCard after the opportunity matrix"
```

---

## Task 6: Docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the endpoint to the API list**

In `CLAUDE.md`, under "## API endpoints", add `/api/v1/articles/volume-trend` to the "Live read endpoints" sentence (next to `/api/v1/articles`).

- [ ] **Step 2: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add CLAUDE.md
git commit -m "docs: note /articles/volume-trend read endpoint"
```

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- Backend endpoint, WIB bucketing, source split, zero-fill, ranges, response model → Task 1.
- Frontend data layer (key, schema, hook, exports, codegen) → Task 2.
- Stacked SVG bars, scales, WIB labels, tooltip, pure helper → Tasks 3 (logic) + 4 (render).
- Placement after opportunity matrix → Task 5.
- Edge cases (empty/loading/error) → Task 4 states + Task 1 empty-DB test.
- Testing (backend pytest, frontend pure-helper `bun test`) → Tasks 1 & 3.
- "No new dep", "implement on fresh branch off master" → Global Constraints + Setup.

**2. Placeholder scan** — no TBD/TODO; every code step contains full code; commands have expected output. The only conditional notes (`generated.ts` regen needs API up; `Skeleton` style fallback; `id-ID` month sanity) are explicit fallbacks, not placeholders.

**3. Type consistency** — `bucket: "hour" | "day"` is consistent across `useVolumeTrend`, `articleKeys.volumeTrend`, `formatBucketLabel`, `Chart`, and `Toggle`. `VolumeBucket` fields (`bucket_start`, `competitor_count`, `internal_count`) match the Pydantic model, the Zod schema, and the helper. `buildVolumeChart` / `Bar` / `ChartDims` names match between Task 3's definition and Task 4's consumption. Backend `_dense_bucket_starts` / `_RANGE` / `_WIB` are self-contained in Task 1.
