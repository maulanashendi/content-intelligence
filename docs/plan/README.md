# Plan: Demand × Performance redesign

Reframes the app around a single editorial question per cluster: **does external
demand exist, and is Tempo capturing it?** Two orthogonal axes — external demand
(Google Trends + competitor RSS) and internal performance (GSC + internal RSS) —
produce a 2×2 matrix; `/morning` ranks the **opportunity** quadrant (high demand,
low/no performance) first.

## Why

Two defects motivated this (see investigation in `decisions.md` D35):

1. **`trend_match_count ≈ 0` everywhere.** Scoring counted trend signals in a
   hardcoded 24h window while clustering is a daily batch over a 7-day (currently
   mis-set 30-day) article window; the two windows never overlapped. It also
   counted `trend_signal` rows (one per 10-min poll) instead of distinct
   keywords, inflating the rare non-zero values ~23×.
2. **Internal performance is dead.** `gsc_page` has ~56k rows but
   `article_gsc_metric` has 0 — GSC raw data is fetched but never mapped to
   articles, so `underperformed` / `tempo_gsc_impressions` are always empty.

## Agreed decisions (2026-06-03)

- Align all windows to **7 days** (cluster = trend = GSC).
- High/low classification via **percentile-relative thresholds per run**.
- GSC→article match adds **trailing-ID fallback** to lift match rate.
- Keep it simple: both scoring halves run in the **single daily cluster cycle**
  (no second scheduler).
- **D35 governance:** expose derived editorial *levels*; keep raw GSC hidden.
- `/morning` ranks by opportunity quadrant; FE gets a new card above the topic
  cluster map.

## PRs

| PR | File | Summary | Depends on |
| -- | ---- | ------- | ---------- |
| PR1 | [pr1-window-alignment-trend-metric-fix.md](pr1-window-alignment-trend-metric-fix.md) | Align windows to 7d; fix trend match semantics (keyword count) | — |
| PR2 | [pr2-gsc-article-link.md](pr2-gsc-article-link.md) | Populate `article_gsc_metric` from `gsc_page` | — |
| PR3 | [pr3-scoring-split-demand-performance.md](pr3-scoring-split-demand-performance.md) | Split scoring into demand + performance; 2×2 quadrant; schema | PR1, PR2 |
| PR4 | [pr4-api-contract-d35.md](pr4-api-contract-d35.md) | API contract + D35 governance; opportunity ranking | PR3 |
| PR5 | [pr5-frontend-opportunity-card.md](pr5-frontend-opportunity-card.md) | "Peluang Editorial" card above topic cluster map | PR4 |

PR1 is independent and ships the immediate fix. PR2 is independent of PR1.
PR3→PR4→PR5 are strictly sequential.
