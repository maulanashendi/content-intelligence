# API Contract

Authoritative HTTP contract between the FastAPI backend (`backend/packages/api/`) and the SPA frontend (`frontend/packages/`). Read this after `schema.dbml` and before `tech-stack.md`.

The contract is the boundary. The backend is free to refactor anything behind it; the frontend is free to evolve any UI behind it. Both sides must keep this document in sync with the implementation.

The MVP API is **read-only with one exception**: `ContentSource` CRUD is permitted on `/api/v1/sources` per `decisions.md` D19. The editorial team needs to add and manage RSS feeds at runtime without a redeploy. Every other table — `article`, `cluster*`, `cluster_run`, `cluster_insight`, `trend_signal`, `article_embedding`, `article_gsc_metric` — is read-only via the API. Pipeline outputs are produced by the daily batch (cron) and the `serve` daemon (D20); the API never writes to them.

---

## 1. Status legend

Every endpoint in this document carries one of two status tags.

| Tag        | Meaning                                                                                                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LIVE`     | Implemented in `backend/packages/api/src/api/routes/`. The contract here describes shipped behavior — code is the tiebreaker if they ever diverge.                        |
| `PROPOSED` | Not implemented. The frontend currently renders dummy data inlined in the route component. The contract here is a forward spec — backend must match it byte-for-byte when implementing. |

`PROPOSED → LIVE` once the backend lands the route, the FE replaces dummy data with the real hook, and `frontend/packages/api/src/generated.ts` is regenerated. All three changes ship together.

## 2. Conventions

### Base URL & versioning

- All paths are prefixed with `/api/v1`.
- The frontend resolves the base via `VITE_API_BASE_URL` (`@ei-fe/core/env.ts`); when FE and BE share an origin, the default is `/api/v1`.
- `v1` is the only version. Breaking changes are made by coordinated FE + BE + `generated.ts` regeneration in a single PR. `v2` is reserved for the day a non-SPA consumer pins to v1 — not an MVP concern.

### Content type

- Responses: `application/json`, UTF-8.
- No request bodies in v1 (no write endpoints).

### Authentication

Per `decisions.md` D10, authentication is handled by the **upstream gateway**. Application code never reads or validates auth tokens. The contract documents no `Authorization` header — it is invisible to both backend and frontend code.

### Error envelope

Non-2xx responses use FastAPI's default error shape:

```json
{ "detail": "Cluster not found" }
```

The frontend (`packages/api/src/client.ts`) reads `detail` if present and otherwise falls back to `HTTP <status>`.

### Request correlation

- Backend SHOULD emit `x-request-id` on every response (success and error).
- Frontend reads `x-request-id` on errors and surfaces it in the `ApiError` instance (`@ei-fe/core`).
- The header is optional; missing it is not itself an error.

### Empty-result semantics

Every list response returns **`200` + `[]`** when there are no rows. The frontend renders an `EmptyState`. There are no `204` or `404` responses for "the list happens to be empty."

The single bundled-object endpoint (`/cluster-runs/latest`) returns `200` with `run: null` and an empty `clusters[]` when no completed run exists yet — same principle, applied to a non-list shape. Never `404`.

The only `404` in v1 is `/clusters/{cluster_id}` for missing or archived clusters.

### Pagination

There is **no pagination in v1**. Every list endpoint returns the full result set bounded by a documented hard cap (e.g. morning is `LIMIT 10`, trend-signals is `LIMIT 50`). If a future endpoint needs pagination, it MUST introduce it as a versioned addition rather than retrofit it on an existing response shape.

### Date / time

- **Wire format: ISO-8601 UTC with the `Z` suffix.** Example: `2026-04-30T06:00:12Z`. Microseconds may be present (`2026-04-30T06:00:12.345678Z`). This is enforced by `api.types.UtcDateTime`, a Pydantic `Annotated` type that wraps every datetime field in API responses; tests assert the trailing `Z` (`test_list_articles_timestamps_carry_utc_z_suffix`, `test_source_timestamps_carry_utc_z_suffix`). Without the `Z`, JS `new Date()` interprets the string as the user's local time, which historically displayed timestamps 7 hours wrong for WIB users.
- **Backend storage**: naive UTC in PostgreSQL `TIMESTAMP` (no time zone column). Conversion to `Z`-tagged on the way out.
- **Frontend display: WIB / Asia/Jakarta (GMT+7).** All user-facing timestamps go through the helpers in `frontend/packages/core/src/format.ts` — `formatDate`, `formatDateTime`, `formatTime`, `formatRelative` — each of which sets `timeZone: "Asia/Jakarta"` and locale `id-ID`. Components must NOT call `new Date(iso).toLocaleString(...)` inline; use the helpers so the timezone is applied uniformly.
- **Defensive parsing**: the helpers tolerate strings without an explicit timezone by treating them as UTC (appending `Z`). This bridges any legacy naive-string callers and avoids regressions if a future endpoint forgets `UtcDateTime`.

### Identifiers

- All `id` fields are `uuid` v4. Path-param UUIDs that fail to parse → `422` from FastAPI's default validator.

### Field nullability convention

- `nullable: yes` means the field is always present in the response; its value MAY be `null`.
- A field listed in the contract MUST always be present (use `null` for missing data, never omit the key). This matches the Zod schemas in `frontend/packages/api/src/schemas.ts`, which use `.nullable()` and would fail on missing keys.

---

## 3. Shared schemas

### `ClusterSummary`

| field            | type    | nullable | notes                                                                  |
| ---------------- | ------- | -------- | ---------------------------------------------------------------------- |
| `id`             | uuid    | no       | `article_cluster.id`                                                   |
| `label`          | string  | yes      | LLM-generated; may be missing for very small clusters                  |
| `member_count`   | integer | yes      | denormalized on `article_cluster`; refreshed per run                   |
| `trend_velocity` | number  | yes      | from `cluster_insight.trend_velocity`; sort key for morning + deferred |
| `novelty_score`  | number  | yes      | 0–1 range; from `cluster_insight.novelty_score`                        |
| `coverage_score` | number  | yes      | 0–1 range; from `cluster_insight.coverage_score`                       |
| `recommendation` | enum    | yes      | `"trending" \| "worth_writing" \| "saturated"`                         |

```json
{
  "id": "a1b2c3d4-0001-4000-8000-000000000001",
  "label": "Q2 rice price hike",
  "member_count": 14,
  "trend_velocity": 0.87,
  "novelty_score": 0.62,
  "coverage_score": 0.31,
  "recommendation": "worth_writing"
}
```

### `Article`

Flat article row for the `/articles` list. Distinct from `ArticleMember` — no cluster context, no `relevance_score`.

| field             | type              | nullable | notes                                                        |
| ----------------- | ----------------- | -------- | ------------------------------------------------------------ |
| `id`              | uuid              | no       | `article.id`                                                 |
| `title`           | string            | no       | from `article.title`                                         |
| `url`             | string            | no       | from `article.url`                                           |
| `first_paragraph` | string            | yes      | from `article.first_paragraph`                               |
| `published_at`    | string (ISO-8601) | yes      | from `article.published_at`                                  |
| `created_at`      | string (ISO-8601) | no       | from `article.created_at`; default sort key                  |
| `source_name`     | string            | no       | denormalized join from `content_source.name`                 |
| `source_type`     | enum              | no       | `"rss" \| "internal"` — from `content_source.source_type`   |

```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "title": "Premium Rice Tops Rp18,000/kg at Wholesale Market",
  "url": "https://kompas.com/berita/abc",
  "first_paragraph": "Premium rice prices at the Cipinang wholesale market…",
  "published_at": "2026-04-28T09:12:00Z",
  "created_at": "2026-04-28T09:15:00Z",
  "source_name": "Kompas",
  "source_type": "rss"
}
```

### `PaginatedArticles`

Envelope returned by `GET /api/v1/articles`.

| field         | type              | nullable | notes                                             |
| ------------- | ----------------- | -------- | ------------------------------------------------- |
| `items`       | array of `Article`| no       | page slice; empty array on an out-of-range page   |
| `total`       | integer           | no       | total rows matching the query (before slicing)    |
| `page`        | integer           | no       | current page number (1-based)                     |
| `page_size`   | integer           | no       | rows per page as applied                          |
| `total_pages` | integer           | no       | `ceil(total / page_size)`; `1` when `total = 0`  |

### `ArticleMember`

| field             | type              | nullable | notes                                              |
| ----------------- | ----------------- | -------- | -------------------------------------------------- |
| `id`              | uuid              | no       | `article.id`                                       |
| `title`           | string            | no       | from `article.title`                               |
| `url`             | string            | no       | from `article.url`                                 |
| `first_paragraph` | string            | yes      | from `article.first_paragraph`                     |
| `published_at`    | string (ISO-8601) | yes      | from `article.published_at`                        |
| `source_name`     | string            | no       | denormalized join from `content_source.name`       |
| `relevance_score` | number            | yes      | from `article_cluster_member.relevance_score`; 0–1 |

```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "title": "Premium Rice Tops Rp18,000/kg at Wholesale Market",
  "url": "https://kompas.com/berita/abc",
  "first_paragraph": "Premium rice prices at the Cipinang wholesale market…",
  "published_at": "2026-04-28T09:12:00Z",
  "source_name": "Kompas",
  "relevance_score": 0.91
}
```

### `ClusterDetail`

Extends `ClusterSummary` with a `members` array.

| field                                  | type                     | nullable | notes                                                   |
| -------------------------------------- | ------------------------ | -------- | ------------------------------------------------------- |
| ...all fields from `ClusterSummary`... |                          |          |                                                         |
| `members`                              | array of `ArticleMember` | no       | empty array if the cluster has no members; never `null` |

### `ContentSource`

Mirrors the `content_source` table.

| field               | type              | nullable | notes                                                                                                                                |
| ------------------- | ----------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `id`                | uuid              | no       |                                                                                                                                      |
| `name`              | string            | no       | display label                                                                                                                        |
| `url`               | string            | no       | unique                                                                                                                               |
| `source_type`       | enum              | no       | `"rss" \| "internal"` — schema-authoritative; no other values exist in v1                                                            |
| `is_enabled`        | boolean           | no       | `true` by default                                                                                                                    |
| `status`            | enum              | yes      | `"active" \| "error" \| "blocked"`                                                                                                   |
| `last_fetched_at`   | string (ISO-8601) | yes      | last successful ingest run                                                                                                           |
| `created_at`        | string (ISO-8601) | no       |                                                                                                                                      |
| `updated_at`        | string (ISO-8601) | no       |                                                                                                                                      |
| `article_count_24h` | integer           | no       | derived: `COUNT(*) FROM article WHERE source_id = ? AND created_at >= now() - interval '24 hours'`. Computed at request time. Not stored. |

### `ClusterRun`

Mirrors `cluster_run`.

| field               | type              | nullable | notes                                                                                                          |
| ------------------- | ----------------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `id`                | uuid              | no       |                                                                                                                |
| `algorithm`         | enum              | yes      | `"hdbscan" \| "kmeans"`                                                                                        |
| `algorithm_version` | string            | yes      | e.g. `"0.8.33"`                                                                                                |
| `params`            | object            | yes      | free-form JSONB; HDBSCAN params, UMAP params, etc. Keys vary by algorithm.                                     |
| `started_at`        | string (ISO-8601) | no       |                                                                                                                |
| `finished_at`       | string (ISO-8601) | yes      | `null` while running; `/cluster-runs/latest` only returns runs where `finished_at IS NOT NULL`, so in practice this field is non-null in that endpoint's response |
| `notes`             | string            | yes      | optional run annotation                                                                                        |

### `ClusterRunCluster`

Cluster-row shape used inside `/cluster-runs/latest`. **Distinct from `ClusterSummary`** — includes `is_current` and `created_at` (the operator view shows archived clusters too) and excludes the morning/deferred metrics (which live under `insight`).

| field          | type                       | nullable | notes                                                                          |
| -------------- | -------------------------- | -------- | ------------------------------------------------------------------------------ |
| `id`           | uuid                       | no       | `article_cluster.id`                                                           |
| `label`        | string                     | yes      |                                                                                |
| `member_count` | integer                    | yes      |                                                                                |
| `is_current`   | boolean                    | no       | from `article_cluster.is_current`                                              |
| `created_at`   | string (ISO-8601)          | no       | from `article_cluster.created_at`                                              |
| `insight`      | `ClusterRunInsight \| null` | yes      | `null` if scoring has not run for this cluster yet                             |

### `ClusterRunInsight`

| field            | type              | nullable | notes                                                                                                       |
| ---------------- | ----------------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `trend_velocity` | number            | yes      |                                                                                                             |
| `novelty_score`  | number            | yes      |                                                                                                             |
| `coverage_score` | number            | yes      |                                                                                                             |
| `recommendation` | enum              | yes      | `"trending" \| "worth_writing" \| "saturated"`                                                              |
| `calculated_at`  | string (ISO-8601) | no       |                                                                                                             |

`cluster_insight.summary` is **not** part of the v1 contract. The column stays in the schema for future use but no endpoint returns it; no FE component reads it.

### `TrendSignal`

| field            | type              | nullable | notes                                                                                                                 |
| ---------------- | ----------------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `id`             | uuid              | no       | `trend_signal.id`                                                                                                     |
| `keyword`        | string            | no       |                                                                                                                       |
| `interest_score` | number            | yes      | 0–100; Google Trends `interest` score                                                                                 |
| `captured_at`    | string (ISO-8601) | no       | snapshot timestamp                                                                                                    |
| `article_count`  | integer           | no       | derived: `COUNT(*) FROM trend_signal_article WHERE trend_signal_id = ?`. Computed at request time. Not stored.        |

`region` is fixed at `"ID"` in v1 (the product is Indonesia-only per PRD); the field exists on the table but is not returned, since every row has the same value. If a future feature adds another region, the field is added as an additive change.

---

## 4. Endpoints — LIVE

### `GET /api/v1/health`

**Status**: LIVE
**Used by**: ops / probes (no FE caller)
**Backed by**: `backend/packages/api/src/api/routes/health.py`

Liveness check. Executes `SELECT 1` to confirm the DB session is reachable.

**Path params** — (none)
**Query params** — (none)

**Response 200**

| field    | type   | nullable | notes              |
| -------- | ------ | -------- | ------------------ |
| `status` | string | no       | always `"ok"` on 200 |

```json
{ "status": "ok" }
```

**Errors**

| status | when                                  | body                |
| ------ | ------------------------------------- | ------------------- |
| 500    | DB session cannot execute `SELECT 1`  | FastAPI default     |

---

### `GET /api/v1/clusters/morning`

**Status**: LIVE
**Used by**: `/morning` route via `useMorningClusters` (`@ei-fe/api`)
**Backed by**: `backend/packages/api/src/api/routes/clusters.py:58-94`

Top 10 clusters Maulana should consider this morning.

**Path params** — (none)
**Query params** — (none)

**Response 200** — `ClusterSummary[]`

The array is at most 10 elements, sorted by `trend_velocity` descending (nulls last). Empty array when no eligible cluster exists.

```json
[
  {
    "id": "a1b2c3d4-0001-4000-8000-000000000001",
    "label": "Q2 rice price hike",
    "member_count": 14,
    "trend_velocity": 0.87,
    "novelty_score": 0.62,
    "coverage_score": 0.31,
    "recommendation": "worth_writing"
  }
]
```

**Errors**

| status | when     | body            |
| ------ | -------- | --------------- |
| 500    | DB error | FastAPI default |

**Notes / constraints**

- Only clusters where `article_cluster.is_current = true`.
- Only clusters whose insight `recommendation` is `trending` or `worth_writing`. Saturated clusters live on `/deferred`.
- Clusters with **any internal article published in the last 30 days** are excluded. "Internal" = `content_source.source_type = 'internal'`.
  **The 30-day window is frozen in v1.** It is hard-coded in the backend SQL and not exposed as a query parameter. PRD §7 #1 listed this as undecided; the contract closes it. Changing the value requires a contract bump and a coordinated FE + BE deploy.
- Empty array is a valid response — the FE renders an `EmptyState` directing the user to `/deferred`.

---

### `GET /api/v1/clusters/deferred`

**Status**: LIVE
**Used by**: `/deferred` route via `useDeferredClusters`
**Backed by**: `backend/packages/api/src/api/routes/clusters.py:97-110`

Saturated clusters — competitors have covered the topic heavily. The desk head reviews this each afternoon.

**Path params** — (none)
**Query params** — (none)

**Response 200** — `ClusterSummary[]`

No upper bound on length; sorted by `trend_velocity` descending (nulls last). Empty array when no saturated cluster exists.

**Errors** — same as `/morning`.

**Notes / constraints**

- Only `is_current = true` clusters.
- Only `recommendation = 'saturated'`.
- The 30-day "internal article" filter does **not** apply here — saturated topics include those Tempo has already written.

---

### `GET /api/v1/clusters/{cluster_id}`

**Status**: LIVE
**Used by**: `/clusters/:id` route via `useClusterDetail`
**Backed by**: `backend/packages/api/src/api/routes/clusters.py:113-165`

Full detail for a single cluster, including its member articles.

**Path params**

| name         | type | required | notes                              |
| ------------ | ---- | -------- | ---------------------------------- |
| `cluster_id` | uuid | yes      | unparseable UUIDs → `422`          |

**Query params** — (none)

**Response 200** — `ClusterDetail`

```json
{
  "id": "a1b2c3d4-0001-4000-8000-000000000001",
  "label": "Q2 rice price hike",
  "member_count": 14,
  "trend_velocity": 0.87,
  "novelty_score": 0.62,
  "coverage_score": 0.31,
  "recommendation": "worth_writing",
  "members": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "title": "Premium Rice Tops Rp18,000/kg at Wholesale Market",
      "url": "https://kompas.com/berita/abc",
      "first_paragraph": "Premium rice prices at the Cipinang wholesale market…",
      "published_at": "2026-04-28T09:12:00Z",
      "source_name": "Kompas",
      "relevance_score": 0.91
    }
  ]
}
```

**Errors**

| status | when                                                                   | body                                      |
| ------ | ---------------------------------------------------------------------- | ----------------------------------------- |
| 404    | cluster does not exist OR exists but `is_current = false`              | `{ "detail": "Cluster not found" }`       |
| 422    | `cluster_id` not a valid UUID                                          | FastAPI default                           |

**Notes / constraints**

- The 404 collapses "missing" and "archived" into one error on purpose: the URL is shareable, and an old cluster id surviving as a deep link should look the same as a typo. The FE renders the same `EmptyState` for both.
- `members` is sorted by `relevance_score` descending (nulls last). Empty array is valid.

---

## 5. Endpoints — PROPOSED

Four new read-only endpoints, all backed by tables that already have data writers in the pipeline. None require a constraints amendment, schema migration, or new dependency. Ship order is independent — pick whichever the FE needs first.

### 5.0 `GET /api/v1/articles`

**Status**: LIVE
**Used by**: `/article` route via `useArticles` (`@ei-fe/api`)
**Backed by**: `backend/packages/api/src/api/routes/articles.py`

Paginated list of all ingested articles, newest first.

**Path params** — (none)

**Query params**

| name        | type    | required | default | notes                                                |
| ----------- | ------- | -------- | ------- | ---------------------------------------------------- |
| `page`      | integer | no       | `1`     | 1-based; values < 1 → `422`                          |
| `page_size` | integer | no       | `20`    | upper bound `100`; values outside `[1, 100]` → `422` |

**Response 200** — `PaginatedArticles`

```json
{
  "items": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "title": "Premium Rice Tops Rp18,000/kg at Wholesale Market",
      "url": "https://kompas.com/berita/abc",
      "first_paragraph": "Premium rice prices at the Cipinang wholesale market…",
      "published_at": "2026-04-28T09:12:00Z",
      "created_at": "2026-04-28T09:15:00Z",
      "source_name": "Kompas",
      "source_type": "rss"
    }
  ],
  "total": 4812,
  "page": 1,
  "page_size": 20,
  "total_pages": 241
}
```

When no articles exist yet:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 1 }
```

**Errors**

| status | when                                          | body            |
| ------ | --------------------------------------------- | --------------- |
| 422    | `page < 1` or `page_size` not in `[1, 100]`   | FastAPI default |
| 500    | DB error                                      | FastAPI default |

**Notes / constraints**

- Default sort: `article.created_at` DESC (most recently ingested first). Sort order is not configurable in v1.
- Both `rss` and `internal` articles are included. There is no filter param in v1.
- `source_name` and `source_type` are derived via join on `content_source`; computed at request time.
- An out-of-range `page` (e.g., `page=999` when only 3 pages exist) returns `200` with `items: []` — not `404`.
- `total_pages` is always at least `1` even when `total = 0`.

---

### 5.1 `GET /api/v1/cluster-runs/latest`

**Status**: PROPOSED
**Used by**: `/clustering` route (currently dummy data in `frontend/packages/app/src/routes/clustering.tsx`)
**Backed by**: not yet implemented

Latest finished cluster run plus all its clusters and per-cluster insights, for the operator-style debug view.

**Path params** — (none)
**Query params** — (none)

**Response 200**

| field                   | type                       | nullable | notes                                                                                                                  |
| ----------------------- | -------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
| `run`                   | `ClusterRun`               | yes      | most-recent row in `cluster_run` ordered by `started_at` DESC where `finished_at IS NOT NULL`. `null` when no completed run exists yet. |
| `clusters`              | array of `ClusterRunCluster` | no    | every cluster belonging to `run` (both `is_current = true` and `false`). Empty array when `run` is `null`.             |
| `summary.current_count` | integer                    | no       | count of `clusters[]` entries where `is_current = true`. Zero when `run` is `null`.                                    |
| `summary.archived_count` | integer                   | no       | count of `clusters[]` entries where `is_current = false`. Zero when `run` is `null`.                                   |

`clusters[]` is sorted by `created_at` ascending so the FE can preserve discovery order without re-sorting.

```json
{
  "run": {
    "id": "cr0001-0000-4000-8000-000000000001",
    "algorithm": "hdbscan",
    "algorithm_version": "0.8.33",
    "params": { "min_cluster_size": 5, "min_samples": 3, "metric": "cosine" },
    "started_at": "2026-04-30T05:58:04Z",
    "finished_at": "2026-04-30T06:02:41Z",
    "notes": "Daily morning run. 4,812 articles, 142 clusters formed."
  },
  "clusters": [
    {
      "id": "ac000001-0000-4000-8000-000000000001",
      "label": "Kenaikan Harga BBM Pertamina",
      "member_count": 23,
      "is_current": true,
      "created_at": "2026-04-30T06:00:12Z",
      "insight": {
        "trend_velocity": 87.5,
        "novelty_score": 0.72,
        "coverage_score": 0.31,
        "recommendation": "trending",
        "calculated_at": "2026-04-30T06:01:55Z"
      }
    }
  ],
  "summary": { "current_count": 142, "archived_count": 87 }
}
```

When no completed run exists yet:

```json
{ "run": null, "clusters": [], "summary": { "current_count": 0, "archived_count": 0 } }
```

**Errors**

| status | when     | body            |
| ------ | -------- | --------------- |
| 500    | DB error | FastAPI default |

**Notes / constraints**

- "Latest" means latest by `started_at`, restricted to runs where `finished_at IS NOT NULL`. An in-progress run is invisible to this endpoint.
- `cluster_insight.summary` is NOT exposed. The field exists in the schema but is not part of the v1 contract.

---

### 5.2 `GET /api/v1/trend-signals/latest`

**Status**: PROPOSED
**Used by**: `/morning` route (`TrendSignalCard`) and `/clustering` route (right rail)
**Backed by**: not yet implemented

Top trending keywords from the most recent capture window, in Indonesia.

**Path params** — (none)

**Query params**

| name    | type    | required | default | notes                                  |
| ------- | ------- | -------- | ------- | -------------------------------------- |
| `limit` | integer | no       | `10`    | upper bound `50`; values > 50 → `422`  |

**Response 200** — `TrendSignal[]`

Sorted by `interest_score` descending (nulls last). All entries share the same `captured_at` (the most recent capture timestamp); if the latest capture has fewer than `limit` rows, the response is shorter — the API does **not** mix multiple captures into one response.

```json
[
  {
    "id": "ts000001-0000-4000-8000-000000000001",
    "keyword": "Kenaikan Harga BBM",
    "interest_score": 94,
    "captured_at": "2026-04-30T06:00:00Z",
    "article_count": 23
  }
]
```

**Errors**

| status | when                          | body            |
| ------ | ----------------------------- | --------------- |
| 422    | `limit` not in `[1, 50]`      | FastAPI default |
| 500    | DB error                      | FastAPI default |

**Notes / constraints**

- `region` is hard-coded to `"ID"` in the SQL (`WHERE region = 'ID'`) and not exposed as a query parameter.
- Empty array when no captures exist yet (e.g. fresh database before the first ingest run). Not a `404`.
- `article_count` is derived per-request via `COUNT(*) FROM trend_signal_article`. It is not denormalized on the table.

---

### 5.3 `GET /api/v1/sources`

**Status**: LIVE
**Used by**: `/sources` route via `useSources` (`@ei-fe/api`)
**Backed by**: `backend/packages/api/src/api/routes/sources.py`

Full list of every content source.

**Path params** — (none)
**Query params** — (none)

**Response 200** — `ContentSource[]`

Sorted by `name` ascending. Empty array when no sources exist (fresh database).

```json
[
  {
    "id": "cs000001-0000-4000-8000-000000000001",
    "name": "Kompas RSS",
    "url": "https://rss.kompas.com/nasional",
    "source_type": "rss",
    "is_enabled": true,
    "status": "active",
    "last_fetched_at": "2026-04-30T06:12:00Z",
    "created_at": "2025-11-01T00:00:00Z",
    "updated_at": "2026-04-30T06:12:00Z",
    "article_count_24h": 142
  }
]
```

**Errors**

| status | when     | body            |
| ------ | -------- | --------------- |
| 500    | DB error | FastAPI default |

**Notes / constraints**

- `source_type` is restricted to `"rss"` and `"internal"` per `docs/schema.dbml`. No other values appear in v1.
- `article_count_24h` = articles ingested in the last 24 hours, measured by `article.created_at` (not `published_at`). Computed at request time. If the source list grows large enough that the per-request count is expensive, the fix is denormalization onto `content_source`, not pagination — the contract shape does not change.

---

### 5.4 `POST /api/v1/sources`

**Status**: LIVE (per `decisions.md` D19)
**Used by**: `/sources/rss` route via `useCreateSource` (`@ei-fe/api`)
**Backed by**: `backend/packages/api/src/api/routes/sources.py`

Add a new RSS source. Always creates with `source_type = "rss"`; the `internal` type is reserved for the Tempo sitemap ingestor and cannot be created via API.

**Request body**

```json
{
  "url": "https://rss.kompas.com/nasional",
  "name": "Kompas Nasional",
  "is_enabled": true
}
```

- `url` — required, validated as `AnyHttpUrl`. Unique constraint on the column.
- `name` — optional, defaults to `""`. Trimmed and truncated to 200 chars server-side.
- `is_enabled` — optional, defaults to `true`. When `true`, the API issues a `pg_notify('rss_source_created', <id>)` so the running `serve` daemon (D20) fetches the feed immediately. The notify is best-effort: a missing or failed listener does not 500 the POST — the next periodic poll picks the source up.
- Any other field — `422`.

**Response 201** — `ContentSource` (same shape as 5.3, with `article_count_24h: 0`).

**Errors**

| status | when                      | body                                              |
| ------ | ------------------------- | ------------------------------------------------- |
| 409    | duplicate `url`           | `{"detail": "URL sudah terdaftar."}`              |
| 422    | invalid body              | FastAPI default                                   |
| 500    | DB error                  | FastAPI default                                   |

---

### 5.5 `PATCH /api/v1/sources/{id}`

**Status**: LIVE (per `decisions.md` D19)
**Used by**: `/sources` route via `useUpdateSourceEnabled` (`@ei-fe/api`)

Toggle a source on or off without deleting it. Only `is_enabled` is patchable in v1.

**Request body**

```json
{ "is_enabled": false }
```

- Any other field — `422`.

**Response 200** — `ContentSource` (full shape with refreshed `article_count_24h`).

**Errors**

| status | when                      | body                                              |
| ------ | ------------------------- | ------------------------------------------------- |
| 404    | unknown id                | `{"detail": "Source tidak ditemukan."}`           |
| 422    | invalid body              | FastAPI default                                   |

---

### 5.6 `DELETE /api/v1/sources/{id}`

**Status**: LIVE (per `decisions.md` D19)
**Used by**: `/sources` route via `useDeleteSource` (`@ei-fe/api`)

Hard delete a source. Refuses to delete a source that has any articles, to keep cluster/embedding/scoring outputs auditable. Toggle `is_enabled = false` instead if the source has produced articles.

**Response 204** — empty body.

**Errors**

| status | when                                  | body                                                            |
| ------ | ------------------------------------- | --------------------------------------------------------------- |
| 404    | unknown id                            | `{"detail": "Source tidak ditemukan."}`                         |
| 409    | source has at least one article       | `{"detail": "Sumber memiliki artikel dan tidak dapat dihapus."}` |

---

## 6. Frontend cleanup required for this contract

The current FE branch (`feat/frontend-spa`) ships routes and dummy data that do not match the v1 contract. Land these alongside the backend work — they cannot be deferred without leaving dead routes in the SPA.

### 6.1 Routes to delete

| File                                                              | Reason                                                                    |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `frontend/packages/app/src/routes/input-api.tsx`                  | No write API + `source_type = 'api'` does not exist in the schema.        |
| `frontend/packages/app/src/routes/check-schema.tsx`               | Pure FE validator with no product purpose; not in PRD §4 happy path.      |

`routes/input-rss.tsx` is retained — it backs the source-creation flow against `POST /api/v1/sources` (D19).

Also remove their entries from `frontend/packages/app/src/app.tsx` (the `createBrowserRouter` array) and any `<Link>`s pointing to them — currently only from `/sources` (the "+ RSS Feed" and "+ API Source" buttons in `routes/sources.tsx`).

### 6.2 Dummy data to replace with hooks

| Route                                                  | Hook to add in `@ei-fe/api` | Endpoint                       |
| ------------------------------------------------------ | --------------------------- | ------------------------------ |
| `routes/clustering.tsx`                                | `useLatestClusterRun`       | `GET /api/v1/cluster-runs/latest` |
| `routes/sources.tsx`                                   | `useSources`                | `GET /api/v1/sources`          |
| `features/morning/trend-signal-card.tsx`               | `useLatestTrendSignals`     | `GET /api/v1/trend-signals/latest` |

For each: add the Zod schema in `frontend/packages/api/src/schemas.ts`, add the query key in `keys.ts`, add the hook in `queries.ts`, regenerate `generated.ts`, and replace the inline constants in the route component with the hook + standard `LoadingState` / `ErrorState` / `EmptyState` handling (mirror what `morning-view.tsx` already does).

### 6.3 Display-only fixes in `routes/sources.tsx`

The dummy data shows `type: "api"` and `type: "sitemap"` badges. These values are not in the v1 contract. After wiring `useSources`, the page renders only `"rss"` and `"internal"` badges; the `TYPE_BADGE` and `TYPE_LABEL` constants must be reduced to those two keys. Tempo's sitemap source appears with `source_type = "internal"` (not `"sitemap"`).

### 6.4 Component to remove

`features/cluster-detail/`'s `cluster-header.tsx`, `audit-trail-card.tsx`, etc. that display `cluster.summary` (the LLM narrative) — drop the rendering of any `summary` field, since it is not in the v1 contract. Confirm by `grep -rn "summary" frontend/packages/features/src/` and removing unused references.

---

## 7. Per-endpoint template

Every new endpoint added to this document MUST follow this shape. Reviewers should reject PRs that omit any required section.

```markdown
### {METHOD} {path}

**Status**: LIVE | PROPOSED
**Used by**: <FE route(s)> via <hook in @ei-fe/api>, or "ops / probes (no FE caller)"
**Backed by**: <code path with line range>, or "not yet implemented"

One-sentence purpose.

**Path params**
| name | type | required | notes |
| (or "(none)") | | | |

**Query params**
| name | type | required | default | notes |
| (or "(none)") | | | | |

**Response {2xx code}** — <shape name>

| field | type | nullable | notes |

\`\`\`json
<minimal but realistic example>
\`\`\`

**Errors**

| status | when | body |

**Notes / constraints**
- bullet list of business rules, ordering invariants, hard caps, exclusions
```

---

## 8. Versioning & breaking-change policy

### What counts as breaking

Any of the following requires a coordinated FE + BE + `generated.ts` PR:

- Removing a field from a response.
- Narrowing a field's type (`number` → `integer`, `nullable: yes` → `nullable: no`).
- Changing the meaning of a field (same name, different semantics).
- Changing the path or method of an existing endpoint.
- Changing the sort order of a list response when the FE depends on it (e.g., `/morning` is sorted by velocity desc; re-sorting by recency would break the morning UI).
- Adding a required query parameter to an existing endpoint.
- Changing the value of a frozen constant (e.g., the 30-day window on `/morning`).

### What counts as additive (safe)

- Adding a new field to a response.
- Adding a new optional query param with a documented default.
- Adding a new endpoint.

### Frontend regeneration workflow

Per `docs/frontend.md` §"Codegen workflow":

1. Backend lands the change.
2. Developer runs `bun run gen:api` from the FE workspace; this rewrites `frontend/packages/api/src/generated.ts` from `/openapi.json`.
3. Developer updates the matching Zod schema in `frontend/packages/api/src/schemas.ts` by hand.
4. Developer updates MSW fixtures under `frontend/packages/api/tests/mocks/`.
5. Developer updates this document — the PR is incomplete without a contract diff.

CI does not run `gen:api`. The generated file lives in version control specifically so the human-reviewed diff is the audit trail of every contract change.

### When to bump `/api/v1` → `/api/v2`

Bump only when a breaking change cannot be made simultaneously across BE and FE — for example, when an external consumer (not just this SPA) is pinned to the current contract. As long as the BE and the SPA ship together, the sane path is to break v1 in one coordinated PR and update this document, rather than maintaining two versions in parallel.

The MVP has exactly one consumer (the SPA). `v2` is a future-tense scenario, not an active concern.
