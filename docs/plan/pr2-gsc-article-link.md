# PR2 — Revive the GSC → article link

**Branch:** `feat/pr2-gsc-article-link`
**Title:** `fix(ingest): map gsc_page to articles, populate article_gsc_metric`
**Depends on:** none — independent of PR1.

## Goal

Populate `article_gsc_metric` so the internal-performance signals
(`underperformed`, GSC impressions, etc.) stop being dead. This is the
foundation PR3 builds on.

## Root cause recap

- `ingest/gsc.py` upserts `gsc_page` / `gsc_query` / `gsc_page_query` (raw GSC by
  URL), but **nothing writes `article_gsc_metric`**, which scoring reads.
- DB: `gsc_page` = 56,083 rows / 11,739 URLs; `article_gsc_metric` = **0**.
- URL shapes are joinable (`https://www.tempo.co/<section>/<slug>-<id>`). Exact
  normalized match links ~30% of clustered internal articles; a trailing-ID
  fallback lifts that.

## Changes

### 1. Mapper (`backend/packages/ingest/src/ingest/gsc.py`)

New `async def link_articles(session: AsyncSession) -> int`:

1. Build normalized lookup from internal articles (join `content_source` where
   `source_type='internal'`).
2. Build normalized lookup from `gsc_page` rows in the current fetch window
   (`period_start`/`period_end`).
3. Match strategy, in order:
   - **exact normalized URL** — lower-case, strip scheme, strip leading
     `www.`/`en.`/`m.`, strip `?…`/`#…`, strip trailing `/`.
   - **trailing numeric ID fallback** — Tempo slugs end in `-<digits>`
     (e.g. `…-2133891`); match on that ID when the path differs.
4. Aggregate matched `gsc_page` rows per article over the window (sum clicks /
   impressions; impression-weighted `avg_position`; recompute `ctr`).
5. Upsert into `article_gsc_metric` keyed by
   `uq_gsc_metric_article_period (article_id, period_start, period_end)`.

Keep it pure-SQL/CTE where practical for speed (11k×3k is fine in Postgres):
a single `INSERT … SELECT` with a normalization expression + `regexp` for the ID
fallback, wrapped in `ON CONFLICT … DO UPDATE`. Log matched/unmatched counts.

> URL normalization belongs in one helper (e.g. `_normalize_url`) reused by both
> exact and fallback paths; unit-test it directly.

### 2. Daemon wiring (`backend/packages/pipeline/src/pipeline/runner.py`)

In `_cluster_worker`, call the mapper right after the GSC fetch:

```python
await _run_gsc_fetch()        # existing
await _link_gsc_articles()    # NEW — wraps ingest.gsc.link_articles
await _run_cluster_label_score()
```

Add `_link_gsc_articles()` mirroring `_run_gsc_fetch()` (own `get_session()`).

### 3. CLI (optional, `pipeline/cli.py` or `ingest/cli.py`)

Expose as an ad-hoc step (e.g. `python -m ingest.cli gsc-link`) for operators,
consistent with the existing per-step debugging surface.

## Tests

- New `backend/packages/ingest/tests/test_gsc_link.py`:
  - `_normalize_url` cases: scheme, `www`/`en`/`m`, query, fragment, trailing slash.
  - trailing-ID fallback matches when path differs but ID is equal.
  - multi-period dedupe → one `article_gsc_metric` row per (article, period).
  - non-internal articles never linked.

## Acceptance criteria

- `pytest packages/ingest/tests/test_gsc_link.py` green.
- Local run → `SELECT count(*) FROM article_gsc_metric` > 0; spot-check a known
  Tempo URL maps to the right article.
- Match rate logged; trailing-ID fallback measurably above exact-only (~30%).

## Notes / non-goals

- Low match rate for very recent articles is expected (GSC lags ~1 day; fresh
  articles have no week of search data). PR3 models that as `too_early`.
- No API change here — `article_gsc_metric` stays internal (constraints.md:73).

## Rollback

Stop calling `_link_gsc_articles()`; `article_gsc_metric` simply stops being
refreshed. No schema change (table already exists).
