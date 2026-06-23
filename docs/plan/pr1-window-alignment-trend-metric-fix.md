# PR1 — Window alignment + trend match metric fix

**Branch:** `feat/pr1-trend-window-fix`
**Title:** `fix(scoring,labeling): 7-day trend window + distinct-keyword match count`
**Depends on:** none — ships independently.

## Goal

Make `trend_match_count` non-zero and meaningful. Today it is ~0 for every
cluster because the scoring window (hardcoded 24h) never overlaps the daily
cluster build (7–30 day article window), and it counts `trend_signal` rows
(one per 10-minute poll) instead of distinct trending keywords.

## Root cause recap

- `scoring/pipeline.py` `_load_trend_match` / `_load_weighted_trend_score` filter
  `ts.captured_at >= now - 24h`. Scoring runs once daily right after clustering;
  the articles in the build trended days ago, so their signals are >24h old.
- The reactive daemon re-inserts a fresh `trend_signal` row every 10 min for a
  still-trending keyword (`captured_at` is in the unique key), so
  `COUNT(DISTINCT trend_signal_id)` counts captures (~23/keyword/day), not topics.
- Measured: 24h window → 5 clusters match; 7d window → 213.

## Changes

### 1. Config (`backend/packages/core/src/core/config.py`)

- Add `analysis_window_days: int = 7` — single source of truth for the
  cluster / trend / GSC analysis window.
- Make `clustering_window_days` resolve from `analysis_window_days` (keep the
  field name for compatibility, or replace usages).
- Add `scoring_trend_window_days: int = 7` (defaults to `analysis_window_days`).

### 2. `.env` / `.env.example`

- **Remove the `CLUSTERING_WINDOW_DAYS=30` override.** D27 point 6 already
  mandated 7; the override is config drift.

### 3. Scoring (`backend/packages/scoring/src/scoring/pipeline.py`)

`_load_trend_match` — change window and counting unit:

```sql
-- window: now - :trend_window  (was :t24h)
-- count distinct KEYWORD, not trend_signal_id
SELECT m.cluster_id, COUNT(DISTINCT ts.keyword) AS trend_match_count
FROM article_cluster_member m
JOIN trend_signal_article tsa ON tsa.article_id = m.article_id
JOIN trend_signal ts          ON ts.id = tsa.trend_signal_id
JOIN article_cluster c        ON c.id = m.cluster_id AND c.is_current = true
WHERE ts.captured_at >= :trend_window
  AND NOT EXISTS (SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id)
GROUP BY m.cluster_id
```

`_load_weighted_trend_score` — dedupe per keyword (take the keyword's peak
interest, not the sum of every 10-min capture):

```sql
SELECT cluster_id, SUM(kw_interest) AS weighted_trend_score
FROM (
  SELECT m.cluster_id, ts.keyword, MAX(ts.interest_score) AS kw_interest
  FROM article_cluster_member m
  JOIN trend_signal_article tsa ON tsa.article_id = m.article_id
  JOIN trend_signal ts          ON ts.id = tsa.trend_signal_id
  JOIN article_cluster c        ON c.id = m.cluster_id AND c.is_current = true
  WHERE ts.captured_at >= :trend_window
    AND NOT EXISTS (SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id)
  GROUP BY m.cluster_id, ts.keyword
) per_kw
GROUP BY cluster_id
```

Pass `trend_window = current_time - timedelta(days=settings.scoring_trend_window_days)`.
Keep `t24h`/`t7d` for the velocity facts (`_load_article_facts`) unchanged.

### 4. Labeling cap (`backend/packages/labeling/src/labeling/pipeline.py:83-117`)

`_select_cluster_ids_for_labeling` mirrors scoring's join (D34). Apply the same
two changes: window `now - scoring_trend_window_days` and
`COUNT(DISTINCT ts.keyword)`. Update the docstring (line 89) accordingly.

## Tests

- `backend/packages/scoring/tests/test_scoring.py`
  - trend match counts **distinct keywords**, not signal rows: insert the same
    keyword with several `captured_at` values → expect count 1, not N.
  - signals older than the window are excluded; within-window included.
  - `weighted_trend_score` uses per-keyword MAX, not sum-over-captures.
- `backend/packages/pipeline/tests/test_labeling_cap.py`
  - rename/adjust the "stale (>24h) excluded" case to ">7d excluded".
  - add a distinct-keyword case.

## Docs

- Add a short decision note (or fold into D35 in PR4) recording the window =
  `analysis_window_days` and keyword-based match semantics, superseding the 24h /
  distinct-`trend_signal_id` definition in D27/D34.

## Acceptance criteria

- `pytest packages/scoring packages/pipeline` green.
- Local `pipeline.cli score` (or `run-daily`) → `cluster_insight.trend_match_count`
  positive for ≳100 clusters (was 2).
- `/api/v1/clusters/morning` returns multiple clusters with `trend_match_count > 0`.

## Rollback

Pure query/config change, no schema. Revert the commit; existing rows are
overwritten on the next scoring run.
