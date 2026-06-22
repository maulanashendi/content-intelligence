# AI Analyst — Frontend Integration & Editorial Redesign

- **Date:** 2026-06-22
- **Status:** Approved (design); ready for implementation plan
- **Scope owner:** Frontend (`frontend/`)
- **Mockup:** `scratchpad/analyst-mockup.html` → Artifact `b3a25fce-dc08-4519-87ce-7ec59ada64d7`

## 1. Context

The `analyst` backend package and its API routes already ship in production:

- `POST /api/v1/analyst/analyze` → `AnalyzeResult` (16 editorial features + 6 user-need scores + editorial feedback)
- `POST /api/v1/analyst/analyze/batch` → `list[AnalyzeResult]`
- `POST /api/v1/analyst/recommendation` → `RecommendationOutput` (filters applied + sample data rows + insights + summary)

A Next.js/shadcn **prototype** of a chatbot exists under `user-need/data-user-need-frontend/` but is not wired into the production Vite frontend and its visual language clashes with our editorial design system. This work brings the capability into the production frontend, redesigned on our own design system, with stronger UX and data visualization — **frontend only, no backend changes**.

## 2. Goals & non-goals

**Goals**
1. A new **AI Analyst** page: a conversational thread where queries return rich, visualized result cards.
2. Strong data visualization for both capabilities (user-needs radar + feature matrix for `/analyze`; ranked bar chart + table for `/recommendation`).
3. Contextual entry points from cluster/article surfaces into the Analyst.
4. Targeted polish of the Morning Brief (shared KPI primitive, spacing rhythm, Analyst entry point).
5. Full adherence to the existing editorial design system, in Bahasa Indonesia.

**Non-goals / constraints (hard)**
- **No new top-level deps.** Viz = inline SVG + `d3` (already a dep); icons = extend `@ei-fe/ui` `icons.ts` (lucide, already used); responses are structured so **no markdown renderer**; motion = CSS only (no framer-motion).
- **Stateless.** The thread is ephemeral client state only. No DB writes, no persistence (respects the read-only API constraint). `sessionStorage` is acceptable for in-session continuity; nothing server-side.
- Backend untouched. The API contract is the source of truth (`/openapi.json`).
- No legacy global CSS classes (`.card`, `.kw-row`) in new components — Tailwind utilities + `@ei-fe/ui` primitives + design tokens only (per CLAUDE.md / `docs/frontend.md`).

## 3. Approved design (summary)

Conversation thread, centered (~860px). Each user query renders as an accent bubble; each assistant reply renders a structured **result card** (not a chat bubble). Composer at the bottom has a **mode switcher** (Analisis Artikel / Rekomendasi) and supports `/analyze` and `/recommendation` slash commands. Empty state = welcome screen with example prompts. "Analisis baru" resets the thread.

**Signature element:** the **User-Needs Radar** — a 6-axis SVG hexagon that reads an article's editorial DNA at a glance, paired with exact-value bars (gestalt + precision).

The design is built entirely from `frontend/packages/app/src/styles/globals.css` tokens (OKLCH warm-paper ground, indigo accent, Geist / Source Serif 4 / JetBrains Mono). Accent is reserved for detected/active/dominant states; Source Serif is reserved for the editorial summary voice; JetBrains Mono for all figures.

## 4. Architecture & file layout

```
packages/api/src/
  schemas.ts          + AnalyzeResultSchema, RecommendationOutputSchema (+ nested) zod schemas
  queries.ts          + useAnalyzeArticle(), useRecommendation() mutations
  index.ts            export new schemas/types/hooks

packages/features/src/analyst/
  analyst-view.tsx          thread orchestration + ephemeral message state
  composer.tsx              mode switch + slash-command input + submit
  message-bubble.tsx        user query bubble
  analyze-result.tsx        scorecard container (title + sections)
  user-needs-radar.tsx      SVG hexagon radar (d3 scales)
  user-needs-bars.tsx       exact-value bars
  feature-matrix.tsx        16 flags grouped into 4 anchors
  feedback-cards.tsx        4 semantic feedback cards
  recommendation-result.tsx filters + bars + table + insights + summary
  ranked-bars.tsx           horizontal bar chart for sample_data
  data.ts                   feature→anchor grouping + EN→ID label maps + need order
  index.ts

packages/ui/src/
  icons.ts                  + Sparkles, Send, Bot, User, BarChart3, Plus (lucide re-export)
  primitives/kpi.tsx        new shared KPI primitive (used by Analyst + Morning Brief)
  primitives/chat/*         (optional) promote message/composer primitives if reused

packages/app/src/
  routes/analyst.tsx        new route
  app.tsx                   + { path: "analyst", element: <AnalystRoute /> }
  mocks/handlers.ts         + MSW handlers for /analyst/analyze and /analyst/recommendation (demo)

packages/ui/src/layout/sidebar.tsx  + "AI Analyst" under Redaksi nav group
```

## 5. API layer

Hand-written zod schemas mirroring `analyst/schemas.py` (the project hand-writes zod in `schemas.ts`; analyst types are **not** in `generated.ts`):

- `FeatureDataSchema = { status: 0|1 (z.number().int()), reasoning: z.string() }`
- `ArticleFeaturesSchema` = object of `f01_breaking … f16_social_buzz`, each `FeatureDataSchema`.
- `EditorialFeedbackSchema = { recommendation_judul, missing_info, bias_check, next_angle: string[] }`
- `UserNeedScoreSchema = { category: string, score: number }`
- `AnalyzeResultSchema = { features: ArticleFeaturesSchema, editorial_feedback, user_needs: UserNeedScoreSchema[] }`
- `RecommendationInsightSchema = { title, insight, action }`
- `RecommendationOutputSchema = { filters_applied: z.record(z.unknown()), sample_data: z.array(z.record(z.unknown())), insights: RecommendationInsightSchema[], summary: string, data_source: string }`

`sample_data` rows are dynamic dicts → typed as `Record<string, unknown>`; the table/chart infer columns at render.

Hooks (mutations, follow existing `apiPost` pattern):
```ts
export function useAnalyzeArticle() {
  return useMutation({
    mutationFn: (body: { title: string; content: string }) =>
      apiPost("/analyst/analyze", body, AnalyzeResultSchema),
  })
}
export function useRecommendation() {
  return useMutation({
    mutationFn: (intent: string) =>
      apiPost("/analyst/recommendation", { intent }, RecommendationOutputSchema),
  })
}
```
Errors surface via `ApiError` (already thrown by `apiPost` on non-2xx / schema mismatch); the view renders them as an in-thread error result with a retry affordance.

**Score scale:** `UserNeedScore.score` scale is unconfirmed (Pydantic `float`). Frontend normalizes defensively: if max score ≤ 1, treat as 0–1 and ×100; else treat as 0–100. Confirm during implementation against a live response.

## 6. Data visualization specs

### 6.1 User-Needs Radar (`user-needs-radar.tsx`)
- Fixed 6 axes in fixed order, EN→ID labels: Update me→"Beri tahu", Educate me→"Edukasi", Give me perspective→"Perspektif", Help me→"Bantu", Inspire me→"Inspirasi", Divert me→"Hibur".
- SVG hexagon: grid rings at 0.25/0.5/0.75/1.0, spokes, data polygon (accent fill @ ~14% + 2px accent stroke), per-axis dots (dominant axis ≥70 → larger dot + violet + bold label).
- Built by generating SVG geometry in code (no hand-authored paths). Polygon draw-in animation; respects `prefers-reduced-motion`.
- Accessible: `role="img"` + `aria-label` summarizing dominant needs; the paired bars provide the screen-reader-friendly exact values.

### 6.2 User-Needs Bars (`user-needs-bars.tsx`)
- One row per need: label / track+fill / mono value. Dominant need gets gradient fill + bold. Fills animate width.

### 6.3 Feature Matrix (`feature-matrix.tsx`)
16 features grouped into 4 anchors (from `analyst/schemas.py` ordering), each with an ID label:

| Anchor (ID) | Features |
|---|---|
| Waktu & Peristiwa | f01 breaking, f02 live/developing, f03 timeless |
| Kedalaman & Konteks | f04 explanatory, f05 data/investigative, f06 author voice, f07 depth analysis, f08 expert quotes |
| Emosi | f09 positive, f10 conflict/tragedy, f11 light/humor |
| Aksi & Format | f12 actionable, f13 collective call, f14 community, f15 listicle, f16 social buzz |

Each flag: status dot + name. Detected (`status===1`) → accent dot + ring, bold name, `reasoning` shown as mono caption. Undetected → ghosted. Column header shows `n/total` detected count.

### 6.4 Recommendation (`recommendation-result.tsx` + `ranked-bars.tsx`)
- **Filter chips** from `filters_applied` (skip null values; humanize keys: category→"kategori", days_lookback→"rentang", etc.).
- **Ranked horizontal bars**: pick the dominant numeric column in `sample_data` (heuristic: a `page_views`/views-like key, else first numeric column); bar width ∝ value/max; color hint by user-need column when present; value labels `toLocaleString("id-ID")`.
- **Data table**: render `sample_data` as a compact table (column union of row keys, humanized headers, numeric cells right-aligned mono, in an `overflow-x:auto` wrapper).
- **Insight cards**: title → insight → "aksi" tag + action text.
- **Summary**: Source Serif paragraph, lead clause emphasized.
- Empty `sample_data` → meaningful empty state ("Tidak ada data untuk filter ini").

## 7. Composer & thread behavior

- Modes: **Analisis Artikel** (`/analyze`) and **Rekomendasi** (`/recommendation`). Switching modes sets the active command; slash commands typed manually also switch mode.
- `/analyze` input collects **title + body** (API requires both; prototype hardcoded the title — we fix this). UX: a title field + body textarea, or first line = title. Decide in implementation; default = single textarea where first line is title, rest is content, with a hint.
- Validation mirrors backend bounds: title 1–200, content 1–20000, intent 3–500. Inline, on submit.
- Submit → optimistic user bubble + loading result skeleton → mutation → result card. `Enter` submits, `Shift+Enter` newline. Loading disables submit.
- "Analisis baru" clears thread + input.
- Errors render as an in-thread error card (cause + retry), never a bare toast.

## 8. Contextual integration

From cluster detail / opportunity surfaces, an **"Analisis draf"** action deep-links to `/analyst` in `/analyze` mode with the cluster/article title prefilled (via router state or `?analyze=` param), focus in the body field. Honest about the constraint: full article bodies are not on the client, so the action primes the title and the editor pastes the draft. No auto-run unless body is present.

## 9. Morning Brief polish

Targeted, not a teardown:
- Extract inline-styled `KpiRow` into a shared `@ei-fe/ui` `Kpi` primitive (label, value, optional delta/sparkline), reused by the Analyst empty/summary surfaces.
- Tighten vertical spacing rhythm to the 4/8px scale; remove ad-hoc inline `padding` where the primitive covers it.
- Add a single entry point to the Analyst from the brief header.
- No layout upheaval; opportunity matrix, force graph, briefing, trend card stay.

## 10. Testing

- `packages/api/tests`: schema tests for `AnalyzeResultSchema` / `RecommendationOutputSchema` (valid + invalid fixtures); MSW handler smoke.
- `packages/features`: render tests for radar (geometry from known scores), feature-matrix grouping/counts, recommendation column inference + empty state, composer validation + submit/loading/error states.
- Reduced-motion path renders final state without animation.
- Verify against a live backend response once (score scale, `sample_data` keys, `filters_applied` keys).

## 11. Risks / open items

- **Score scale** of `user_needs` (§5) — confirm against live response.
- **`sample_data` shape** is dynamic — column inference must degrade gracefully for unexpected keys; log + render table-only if no numeric column for the bar chart.
- **`filters_applied` keys** — maintain a humanization map with a sensible fallback (raw key) for unknown keys.
- Demo (GitHub Pages) needs MSW mocks for the two endpoints so the Analyst is functional offline.
