# AI Analyst Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "AI Analyst" page to the production frontend — a conversational thread that renders the existing `/api/v1/analyst/*` responses as richly visualized editorial result cards — plus targeted Morning Brief polish.

**Architecture:** New `analyst` feature package under `frontend/packages/features/src/analyst/`, fed by two new mutation hooks + zod schemas in `@ei-fe/api`. All visualization is inline SVG + CSS using the existing OKLCH design tokens; pure logic (schema parsing, feature grouping, radar geometry, column inference) lives in testable helpers. The thread is ephemeral client state — no persistence, no backend changes.

**Tech Stack:** React 19, TanStack Query (mutations), zod, `d3` (already a dep, used only for scales/geometry), MSW (demo mocks), `bun test` (unit tests). Icons via `@ei-fe/ui` lucide re-exports.

## Global Constraints

- **No new top-level deps.** Viz = inline SVG + existing `d3`; icons = extend `@ei-fe/ui/src/icons.ts` (lucide already transitively present); no markdown lib; motion = CSS only (no framer-motion). Any new dep requires updating `docs/tech-stack.md` (avoid).
- **Stateless / read-only.** Thread is ephemeral React state. No DB writes, no server persistence. `sessionStorage` allowed for in-session continuity only.
- **No legacy global CSS classes** (`.card`, `.kpi`, `.kw-row`, etc.) in new components. Use Tailwind utilities + inline `style={{ ... "var(--token)" }}` (the pattern in `opportunity-matrix-card.tsx`) + `@ei-fe/ui` primitives. New shared primitives go in `@ei-fe/ui`.
- **Bahasa Indonesia** UI copy throughout. Editorial design tokens from `frontend/packages/app/src/styles/globals.css`.
- **API contract is source of truth.** Endpoints: `POST /api/v1/analyst/analyze` → `AnalyzeResult`; `POST /api/v1/analyst/recommendation` → `RecommendationOutput`. Request/response shapes mirror `backend/packages/analyst/src/analyst/schemas.py`. `env.apiBase` already includes `/api/v1`, so hook paths are `/analyst/...`.
- **Testing convention:** pure logic → `bun test` (`import { describe, test, expect } from "bun:test"`). Components/wiring → TypeScript build (`bun run build`) + visual verification (dev server / Playwright). There is no React render-test infra; do **not** add testing-library.
- **Commits:** end messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work on a feature branch, not `master`.

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

Run from repo root:
```bash
git checkout -b feat/ai-analyst-frontend
```

---

### Task 1: API schemas (zod) for analyst responses

**Files:**
- Modify: `frontend/packages/api/src/schemas.ts` (append)
- Modify: `frontend/packages/api/src/index.ts` (export)
- Test: `frontend/packages/api/tests/analyst-schemas.test.ts` (create)

**Interfaces:**
- Produces: `AnalyzeResultSchema`, `RecommendationOutputSchema` (zod), and inferred types `AnalyzeResult`, `RecommendationOutput`, `UserNeedScore`, `ArticleFeatures`, `FeatureData`, `EditorialFeedback`, `RecommendationInsight`.

- [ ] **Step 1: Write the failing test**

Create `frontend/packages/api/tests/analyst-schemas.test.ts`:
```ts
import { describe, test, expect } from "bun:test"
import { AnalyzeResultSchema, RecommendationOutputSchema } from "../src/schemas.js"

const VALID_ANALYZE = {
  features: Object.fromEntries(
    [
      "f01_breaking","f02_live_developing","f03_timeless","f04_explanatory",
      "f05_data_investigative","f06_author_voice","f07_depth_analysis","f08_expert_quotes",
      "f09_emotional_positive","f10_conflict_tragedy","f11_light_humor","f12_actionable_steps",
      "f13_collective_call","f14_community_identity","f15_listicle_format","f16_social_buzz",
    ].map((k, i) => [k, { status: i % 2, reasoning: "alasan" }]),
  ),
  editorial_feedback: { recommendation_judul: ["A"], missing_info: [], bias_check: [], next_angle: ["B"] },
  user_needs: [{ category: "Educate me", score: 88 }, { category: "Help me", score: 25 }],
}

const VALID_RECO = {
  filters_applied: { category: "Ekonomi", days_lookback: 7 },
  sample_data: [{ judul: "Kurs Rupiah", page_views: 142300, user_need: "Update me" }],
  insights: [{ title: "T", insight: "I", action: "A" }],
  summary: "ringkasan",
  data_source: "airflow_json",
}

describe("AnalyzeResultSchema", () => {
  test("accepts a valid analyze payload", () => {
    expect(AnalyzeResultSchema.safeParse(VALID_ANALYZE).success).toBe(true)
  })
  test("rejects a feature missing reasoning", () => {
    const bad = structuredClone(VALID_ANALYZE)
    delete (bad.features.f01_breaking as { reasoning?: string }).reasoning
    expect(AnalyzeResultSchema.safeParse(bad).success).toBe(false)
  })
})

describe("RecommendationOutputSchema", () => {
  test("accepts a valid recommendation payload", () => {
    expect(RecommendationOutputSchema.safeParse(VALID_RECO).success).toBe(true)
  })
  test("accepts arbitrary sample_data row shapes", () => {
    const r = structuredClone(VALID_RECO)
    r.sample_data = [{ anything: 1 }, { else: "x", n: 2 }]
    expect(RecommendationOutputSchema.safeParse(r).success).toBe(true)
  })
})
```

- [ ] **Step 2: Run it; verify it fails**

Run: `cd frontend && bun test packages/api/tests/analyst-schemas.test.ts`
Expected: FAIL — `AnalyzeResultSchema` is not exported.

- [ ] **Step 3: Implement the schemas**

Append to `frontend/packages/api/src/schemas.ts`:
```ts
// ── Analyst ───────────────────────────────────────────────────────────────
export const FeatureDataSchema = z.object({
  status: z.number().int(),
  reasoning: z.string(),
})
export type FeatureData = z.infer<typeof FeatureDataSchema>

export const FEATURE_KEYS = [
  "f01_breaking","f02_live_developing","f03_timeless","f04_explanatory",
  "f05_data_investigative","f06_author_voice","f07_depth_analysis","f08_expert_quotes",
  "f09_emotional_positive","f10_conflict_tragedy","f11_light_humor","f12_actionable_steps",
  "f13_collective_call","f14_community_identity","f15_listicle_format","f16_social_buzz",
] as const

export const ArticleFeaturesSchema = z.object(
  Object.fromEntries(FEATURE_KEYS.map((k) => [k, FeatureDataSchema])) as Record<
    (typeof FEATURE_KEYS)[number],
    typeof FeatureDataSchema
  >,
)
export type ArticleFeatures = z.infer<typeof ArticleFeaturesSchema>

export const EditorialFeedbackSchema = z.object({
  recommendation_judul: z.array(z.string()),
  missing_info: z.array(z.string()),
  bias_check: z.array(z.string()),
  next_angle: z.array(z.string()),
})
export type EditorialFeedback = z.infer<typeof EditorialFeedbackSchema>

export const UserNeedScoreSchema = z.object({
  category: z.string(),
  score: z.number(),
})
export type UserNeedScore = z.infer<typeof UserNeedScoreSchema>

export const AnalyzeResultSchema = z.object({
  features: ArticleFeaturesSchema,
  editorial_feedback: EditorialFeedbackSchema,
  user_needs: z.array(UserNeedScoreSchema),
})
export type AnalyzeResult = z.infer<typeof AnalyzeResultSchema>

export const RecommendationInsightSchema = z.object({
  title: z.string(),
  insight: z.string(),
  action: z.string(),
})
export type RecommendationInsight = z.infer<typeof RecommendationInsightSchema>

export const RecommendationOutputSchema = z.object({
  filters_applied: z.record(z.unknown()),
  sample_data: z.array(z.record(z.unknown())),
  insights: z.array(RecommendationInsightSchema),
  summary: z.string(),
  data_source: z.string(),
})
export type RecommendationOutput = z.infer<typeof RecommendationOutputSchema>
```

- [ ] **Step 4: Export from the package index**

In `frontend/packages/api/src/index.ts`, add to the existing type export line and value export line:
```ts
export type { AnalyzeResult, RecommendationOutput, UserNeedScore, ArticleFeatures, FeatureData, EditorialFeedback, RecommendationInsight } from "./schemas.js"
export { AnalyzeResultSchema, RecommendationOutputSchema, UserNeedScoreSchema, ArticleFeaturesSchema, FeatureDataSchema, EditorialFeedbackSchema, RecommendationInsightSchema, FEATURE_KEYS } from "./schemas.js"
```

- [ ] **Step 5: Run the test; verify it passes**

Run: `cd frontend && bun test packages/api/tests/analyst-schemas.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/api/src/schemas.ts frontend/packages/api/src/index.ts frontend/packages/api/tests/analyst-schemas.test.ts
git commit -m "feat(api): zod schemas for analyst analyze + recommendation"
```

---

### Task 2: API mutation hooks

**Files:**
- Modify: `frontend/packages/api/src/queries.ts` (append; extend imports)
- Modify: `frontend/packages/api/src/index.ts` (export)

**Interfaces:**
- Consumes: `apiPost` (`client.ts`), `AnalyzeResultSchema`, `RecommendationOutputSchema` (Task 1).
- Produces: `useAnalyzeArticle()` → mutation with `mutateAsync(body: { title: string; content: string }): Promise<AnalyzeResult>`; `useRecommendation()` → mutation with `mutateAsync(intent: string): Promise<RecommendationOutput>`.

- [ ] **Step 1: Implement the hooks**

In `frontend/packages/api/src/queries.ts`, extend the schema import to include `AnalyzeResultSchema, RecommendationOutputSchema`, then append:
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

- [ ] **Step 2: Export from index**

In `frontend/packages/api/src/index.ts`, add `useAnalyzeArticle, useRecommendation` to the `queries.js` export list.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && bun run build`
Expected: build succeeds (no TS errors). (Hooks have no isolated unit test — there is no React test infra; they are exercised by visual verification in Task 13.)

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/api/src/queries.ts frontend/packages/api/src/index.ts
git commit -m "feat(api): useAnalyzeArticle + useRecommendation mutation hooks"
```

---

### Task 3: Analyst pure-logic helpers (`data.ts`)

This is the tested core: feature grouping, EN→ID label maps, user-need ordering + score normalization, radar geometry, sample_data column inference, and filter humanization.

**Files:**
- Create: `frontend/packages/features/src/analyst/data.ts`
- Test: `frontend/packages/features/tests/analyst-data.test.ts` (create)
- Modify: `frontend/packages/features/package.json` (add `"zod"`? No — only if used. Not needed; helpers are dep-free except types from `@ei-fe/api`.)

**Interfaces:**
- Produces:
  - `USER_NEED_ORDER: { key: string; label: string }[]` (6 entries, fixed order)
  - `orderedUserNeeds(scores: UserNeedScore[]): { key: string; label: string; value: number }[]` — 6 in fixed order, `value` normalized to 0–100, dominant flag derivable by caller (`value >= 70`)
  - `FEATURE_ANCHORS: { id: string; label: string; keys: string[] }[]` (4 groups)
  - `featureLabel(key: string): string`
  - `groupedFeatures(features: ArticleFeatures): { id: string; label: string; flags: { key: string; name: string; on: boolean; reasoning: string }[]; detected: number }[]`
  - `radarPoints(values: number[], cx: number, cy: number, r: number): [number, number][]` — pure geometry, first axis points up, clockwise
  - `inferNumericColumn(rows: Record<string, unknown>[]): string | null` — picks a views-like numeric column, else first numeric column, else null
  - `humanizeFilterKey(key: string): string`
  - `activeFilters(filters: Record<string, unknown>): { key: string; label: string; value: string }[]` — skips null/undefined

- [ ] **Step 1: Write the failing test**

Create `frontend/packages/features/tests/analyst-data.test.ts`:
```ts
import { describe, test, expect } from "bun:test"
import {
  orderedUserNeeds, groupedFeatures, radarPoints, inferNumericColumn,
  activeFilters, USER_NEED_ORDER, FEATURE_ANCHORS,
} from "../src/analyst/data.js"

describe("orderedUserNeeds", () => {
  test("returns the 6 needs in fixed order with ID labels", () => {
    const out = orderedUserNeeds([{ category: "Educate me", score: 88 }])
    expect(out).toHaveLength(6)
    expect(out.map((n) => n.label)).toEqual(USER_NEED_ORDER.map((n) => n.label))
    expect(out.find((n) => n.key === "Educate me")!.value).toBe(88)
    expect(out.find((n) => n.key === "Help me")!.value).toBe(0) // missing → 0
  })
  test("normalizes 0–1 scores to 0–100", () => {
    const out = orderedUserNeeds([
      { category: "Educate me", score: 0.88 },
      { category: "Help me", score: 0.25 },
    ])
    expect(out.find((n) => n.key === "Educate me")!.value).toBe(88)
  })
})

describe("groupedFeatures", () => {
  test("groups 16 features into 4 anchors and counts detected", () => {
    const feats = Object.fromEntries(
      FEATURE_ANCHORS.flatMap((a) => a.keys).map((k, i) => [k, { status: i < 5 ? 1 : 0, reasoning: "r" }]),
    )
    const groups = groupedFeatures(feats as never)
    expect(groups).toHaveLength(4)
    expect(groups.reduce((s, g) => s + g.flags.length, 0)).toBe(16)
    expect(groups.reduce((s, g) => s + g.detected, 0)).toBe(5)
  })
})

describe("radarPoints", () => {
  test("first axis points straight up from center", () => {
    const pts = radarPoints([100, 0, 0, 0, 0, 0], 100, 100, 80)
    expect(pts[0][0]).toBeCloseTo(100, 1) // same x as center
    expect(pts[0][1]).toBeCloseTo(20, 1)  // cy - r
  })
})

describe("inferNumericColumn", () => {
  test("prefers a views-like column", () => {
    expect(inferNumericColumn([{ judul: "a", page_views: 10, x: 3 }])).toBe("page_views")
  })
  test("falls back to first numeric column", () => {
    expect(inferNumericColumn([{ judul: "a", skor: 5 }])).toBe("skor")
  })
  test("returns null when no numeric column", () => {
    expect(inferNumericColumn([{ judul: "a", kategori: "b" }])).toBeNull()
  })
})

describe("activeFilters", () => {
  test("humanizes keys and skips null", () => {
    const out = activeFilters({ category: "Ekonomi", days_lookback: 7, author: null })
    expect(out.map((f) => f.key)).toEqual(["category", "days_lookback"])
    expect(out[0].label).toBe("kategori")
  })
})
```

- [ ] **Step 2: Run it; verify it fails**

Run: `cd frontend && bun test packages/features/tests/analyst-data.test.ts`
Expected: FAIL — module `../src/analyst/data.js` not found.

- [ ] **Step 3: Implement `data.ts`**

Create `frontend/packages/features/src/analyst/data.ts`:
```ts
import type { ArticleFeatures, UserNeedScore } from "@ei-fe/api"

export const USER_NEED_ORDER = [
  { key: "Update me", label: "Beri tahu" },
  { key: "Educate me", label: "Edukasi" },
  { key: "Give me perspective", label: "Perspektif" },
  { key: "Help me", label: "Bantu" },
  { key: "Inspire me", label: "Inspirasi" },
  { key: "Divert me", label: "Hibur" },
] as const

export function orderedUserNeeds(
  scores: UserNeedScore[],
): { key: string; label: string; value: number }[] {
  const max = scores.reduce((m, s) => Math.max(m, s.score), 0)
  const scale = max > 0 && max <= 1 ? 100 : 1
  const byKey = new Map(scores.map((s) => [s.category.toLowerCase(), s.score]))
  return USER_NEED_ORDER.map((n) => {
    const raw = byKey.get(n.key.toLowerCase()) ?? 0
    return { key: n.key, label: n.label, value: Math.round(Math.min(100, Math.max(0, raw * scale))) }
  })
}

export const FEATURE_ANCHORS: { id: string; label: string; keys: string[] }[] = [
  { id: "time", label: "Waktu & Peristiwa", keys: ["f01_breaking", "f02_live_developing", "f03_timeless"] },
  { id: "depth", label: "Kedalaman & Konteks", keys: ["f04_explanatory", "f05_data_investigative", "f06_author_voice", "f07_depth_analysis", "f08_expert_quotes"] },
  { id: "emotion", label: "Emosi", keys: ["f09_emotional_positive", "f10_conflict_tragedy", "f11_light_humor"] },
  { id: "action", label: "Aksi & Format", keys: ["f12_actionable_steps", "f13_collective_call", "f14_community_identity", "f15_listicle_format", "f16_social_buzz"] },
]

const FEATURE_LABELS: Record<string, string> = {
  f01_breaking: "Breaking / spot news",
  f02_live_developing: "Live / berkembang",
  f03_timeless: "Evergreen",
  f04_explanatory: "Explainer",
  f05_data_investigative: "Data / investigatif",
  f06_author_voice: "Suara penulis / opini",
  f07_depth_analysis: "Analisis dampak",
  f08_expert_quotes: "Kutipan ahli",
  f09_emotional_positive: "Positif / inspiratif",
  f10_conflict_tragedy: "Konflik / tragedi",
  f11_light_humor: "Ringan / humor",
  f12_actionable_steps: "Langkah praktis",
  f13_collective_call: "Ajakan kolektif",
  f14_community_identity: "Identitas komunitas",
  f15_listicle_format: "Listicle",
  f16_social_buzz: "Viral sosial",
}

export function featureLabel(key: string): string {
  return FEATURE_LABELS[key] ?? key
}

export function groupedFeatures(features: ArticleFeatures) {
  const f = features as unknown as Record<string, { status: number; reasoning: string }>
  return FEATURE_ANCHORS.map((a) => {
    const flags = a.keys.map((k) => ({
      key: k,
      name: featureLabel(k),
      on: f[k]?.status === 1,
      reasoning: f[k]?.reasoning ?? "",
    }))
    return { id: a.id, label: a.label, flags, detected: flags.filter((x) => x.on).length }
  })
}

export function radarPoints(
  values: number[],
  cx: number,
  cy: number,
  r: number,
): [number, number][] {
  const n = values.length
  return values.map((v, i) => {
    const angle = (-90 + i * (360 / n)) * (Math.PI / 180)
    const radius = (Math.min(100, Math.max(0, v)) / 100) * r
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]
  })
}

const VIEWS_HINTS = ["page_views", "pageviews", "views", "pv", "reads"]

export function inferNumericColumn(rows: Record<string, unknown>[]): string | null {
  if (rows.length === 0) return null
  const keys = Object.keys(rows[0])
  const isNum = (k: string) => rows.every((row) => typeof row[k] === "number")
  const hinted = keys.find((k) => VIEWS_HINTS.includes(k.toLowerCase()) && isNum(k))
  if (hinted) return hinted
  return keys.find((k) => isNum(k)) ?? null
}

const FILTER_LABELS: Record<string, string> = {
  category: "kategori",
  user_need_category: "kebutuhan",
  min_page_views: "min. views",
  author: "penulis",
  days_lookback: "rentang",
}

export function humanizeFilterKey(key: string): string {
  return FILTER_LABELS[key] ?? key.replace(/_/g, " ")
}

export function activeFilters(
  filters: Record<string, unknown>,
): { key: string; label: string; value: string }[] {
  return Object.entries(filters)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([key, v]) => ({
      key,
      label: humanizeFilterKey(key),
      value: key === "days_lookback" ? `${String(v)} hari` : String(v),
    }))
}
```

- [ ] **Step 4: Run the test; verify it passes**

Run: `cd frontend && bun test packages/features/tests/analyst-data.test.ts`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/features/src/analyst/data.ts frontend/packages/features/tests/analyst-data.test.ts
git commit -m "feat(analyst): pure-logic helpers (grouping, needs, radar geometry, inference)"
```

---

### Task 4: Extend `@ei-fe/ui` icons

**Files:**
- Modify: `frontend/packages/ui/src/icons.ts`

**Interfaces:**
- Produces: re-exported icons `Sparkles`, `Send`, `Bot`, `User`, `BarChart3`, `Plus`, `ArrowUp` from `@ei-fe/ui`.

- [ ] **Step 1: Add the icons**

Replace the export block in `frontend/packages/ui/src/icons.ts`:
```ts
export {
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  ExternalLink,
  AlertCircle,
  Inbox,
  Clock,
  TrendingUp,
  Loader2,
  ArrowLeft,
  Sparkles,
  Send,
  Bot,
  User,
  BarChart3,
  Plus,
  ArrowUp,
} from "lucide-react"
```

- [ ] **Step 2: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/ui/src/icons.ts
git commit -m "feat(ui): add analyst chat icons to curated icon set"
```

---

### Task 5: User-Needs Radar component

**Files:**
- Create: `frontend/packages/features/src/analyst/user-needs-radar.tsx`

**Interfaces:**
- Consumes: `radarPoints`, `orderedUserNeeds` output (Task 3).
- Produces: `<UserNeedsRadar needs={{ key; label; value }[]} />` — SVG hexagon.

- [ ] **Step 1: Implement the component**

Create `frontend/packages/features/src/analyst/user-needs-radar.tsx`:
```tsx
import { radarPoints } from "./data.js"

interface Need { key: string; label: string; value: number }

const VB = { w: 320, h: 250, cx: 160, cy: 116, r: 84 }

export function UserNeedsRadar({ needs }: { needs: Need[] }) {
  const values = needs.map((n) => n.value)
  const ring = (f: number) =>
    radarPoints(needs.map(() => f * 100), VB.cx, VB.cy, VB.r)
      .map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`)
      .join(" ")
  const dataPts = radarPoints(values, VB.cx, VB.cy, VB.r)
  const dom = needs.map((n) => n.value >= 70)
  const labelPts = radarPoints(needs.map(() => 100 + 26), VB.cx, VB.cy, VB.r) // r+26 for labels

  return (
    <svg
      viewBox={`0 0 ${VB.w} ${VB.h}`}
      width="248"
      height="194"
      role="img"
      aria-label={`Radar kebutuhan pembaca. Dominan: ${needs.filter((n) => n.value >= 70).map((n) => `${n.label} ${n.value}`).join(", ") || "tidak ada"}.`}
    >
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke="var(--line)" strokeWidth="1" />
      ))}
      {dataPts.map((_, i) => {
        const spoke = radarPoints(needs.map((_, j) => (j === i ? 100 : 0)), VB.cx, VB.cy, VB.r)[i]
        return <line key={i} x1={VB.cx} y1={VB.cy} x2={spoke[0]} y2={spoke[1]} stroke="var(--line)" strokeWidth="1" />
      })}
      <polygon
        points={dataPts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")}
        fill="oklch(0.55 0.15 262 / 0.14)"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {dataPts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={dom[i] ? 4 : 2.6}
          fill={dom[i] ? "oklch(0.45 0.18 285)" : "var(--accent)"} />
      ))}
      {needs.map((n, i) => {
        const lp = labelPts[i]
        const anchor = lp[0] < VB.cx - 10 ? "end" : lp[0] > VB.cx + 10 ? "start" : "middle"
        return (
          <text key={n.key} x={lp[0]} y={lp[1] + 3} textAnchor={anchor}
            fontFamily="var(--font-mono)" fontSize="10"
            fill={dom[i] ? "var(--accent-fg)" : "var(--fg-muted)"}
            fontWeight={dom[i] ? 600 : 400}>
            {n.label}
          </text>
        )
      })}
    </svg>
  )
}
```

- [ ] **Step 2: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/user-needs-radar.tsx
git commit -m "feat(analyst): user-needs radar (SVG hexagon)"
```

(Visual verification happens in Task 13 once the page is reachable.)

---

### Task 6: User-Needs Bars component

**Files:**
- Create: `frontend/packages/features/src/analyst/user-needs-bars.tsx`

**Interfaces:**
- Produces: `<UserNeedsBars needs={Need[]} />`.

- [ ] **Step 1: Implement**

Create `frontend/packages/features/src/analyst/user-needs-bars.tsx`:
```tsx
interface Need { key: string; label: string; value: number }

export function UserNeedsBars({ needs }: { needs: Need[] }) {
  return (
    <div className="flex flex-col gap-2.5">
      {needs.map((n) => {
        const dom = n.value >= 70
        return (
          <div key={n.key} className="grid items-center gap-2.5" style={{ gridTemplateColumns: "84px 1fr 30px" }}>
            <span className="text-[12px]" style={{ color: "var(--fg)", fontWeight: dom ? 600 : 400 }}>{n.label}</span>
            <span className="h-[7px] rounded-[3px] overflow-hidden" style={{ background: "var(--bg-sunken)", border: "1px solid var(--line)" }}>
              <span className="block h-full rounded-[2px] transition-[width] duration-700"
                style={{ width: `${n.value}%`, background: dom ? "linear-gradient(90deg, var(--accent), oklch(0.45 0.18 285))" : "var(--accent)" }} />
            </span>
            <span className="text-[11.5px] text-right tabular-nums" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-muted)" }}>{n.value}</span>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/user-needs-bars.tsx
git commit -m "feat(analyst): user-needs exact-value bars"
```

---

### Task 7: Feature Matrix component

**Files:**
- Create: `frontend/packages/features/src/analyst/feature-matrix.tsx`

**Interfaces:**
- Consumes: `groupedFeatures` (Task 3).
- Produces: `<FeatureMatrix features={ArticleFeatures} />`.

- [ ] **Step 1: Implement**

Create `frontend/packages/features/src/analyst/feature-matrix.tsx`:
```tsx
import type { ArticleFeatures } from "@ei-fe/api"
import { groupedFeatures } from "./data.js"

export function FeatureMatrix({ features }: { features: ArticleFeatures }) {
  const groups = groupedFeatures(features)
  return (
    <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
      {groups.map((g) => (
        <div key={g.id}>
          <div className="flex justify-between pb-1.5 mb-2" style={{ borderBottom: "1px solid var(--line)" }}>
            <span className="text-[9.5px] uppercase tracking-[0.05em]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>{g.label}</span>
            <span className="text-[9.5px]" style={{ fontFamily: "var(--font-mono)", color: "var(--accent-fg)" }}>{g.detected}/{g.flags.length}</span>
          </div>
          {g.flags.map((f) => (
            <div key={f.key} className="flex gap-2 py-1 items-start">
              <span className="w-[7px] h-[7px] rounded-full shrink-0 mt-[5px]"
                style={f.on
                  ? { background: "var(--accent)", boxShadow: "0 0 0 3px var(--accent-soft)" }
                  : { background: "var(--bg-sunken)", border: "1px solid var(--line-strong)" }} />
              <span className="min-w-0">
                <span className="block text-[11.5px] leading-tight" style={{ color: f.on ? "var(--fg)" : "var(--fg-ghost)", fontWeight: f.on ? 500 : 400 }}>{f.name}</span>
                {f.on && f.reasoning && (
                  <span className="block text-[9.5px] mt-0.5 leading-snug" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>{f.reasoning}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/feature-matrix.tsx
git commit -m "feat(analyst): 16-feature editorial matrix grouped by anchor"
```

---

### Task 8: Editorial Feedback cards

**Files:**
- Create: `frontend/packages/features/src/analyst/feedback-cards.tsx`

**Interfaces:**
- Consumes: `EditorialFeedback` type (Task 1).
- Produces: `<FeedbackCards feedback={EditorialFeedback} />`.

- [ ] **Step 1: Implement**

Create `frontend/packages/features/src/analyst/feedback-cards.tsx`:
```tsx
import type { EditorialFeedback } from "@ei-fe/api"

type Tone = "judul" | "info" | "bias" | "angle"
const STYLES: Record<Tone, { bg: string; border: string; head: string; dot: string }> = {
  judul: { bg: "var(--accent-soft)", border: "oklch(0.55 0.15 262 / 0.25)", head: "var(--accent-fg)", dot: "var(--accent)" },
  info:  { bg: "var(--warn-soft)",   border: "oklch(0.72 0.15 75 / 0.3)",   head: "oklch(0.45 0.13 75)", dot: "var(--warn)" },
  bias:  { bg: "var(--bad-soft)",    border: "oklch(0.58 0.18 25 / 0.25)",  head: "var(--bad)", dot: "var(--bad)" },
  angle: { bg: "var(--info-soft)",   border: "oklch(0.60 0.12 230 / 0.25)", head: "oklch(0.42 0.13 230)", dot: "var(--info)" },
}

function Card({ tone, title, items }: { tone: Tone; title: string; items: string[] }) {
  if (!items || items.length === 0) return null
  const s = STYLES[tone]
  return (
    <div className="rounded-[6px] p-3" style={{ background: s.bg, border: `1px solid ${s.border}` }}>
      <p className="text-[10px] font-bold uppercase tracking-[0.05em] mb-1.5" style={{ color: s.head }}>{title}</p>
      <ul className="flex flex-col gap-1.5 m-0 p-0 list-none">
        {items.map((it, i) => (
          <li key={i} className="text-[12px] leading-snug pl-3 relative" style={{ color: "var(--fg-muted)" }}>
            <span className="absolute left-0.5 top-[7px] w-1 h-1 rounded-full" style={{ background: s.dot }} />
            {it}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function FeedbackCards({ feedback }: { feedback: EditorialFeedback }) {
  return (
    <div className="grid gap-2.5" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
      <Card tone="judul" title="Saran Judul" items={feedback.recommendation_judul} />
      <Card tone="info" title="Informasi Kurang" items={feedback.missing_info} />
      <Card tone="bias" title="Cek Bias" items={feedback.bias_check} />
      <Card tone="angle" title="Angle Lanjutan" items={feedback.next_angle} />
    </div>
  )
}
```

- [ ] **Step 2: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/feedback-cards.tsx
git commit -m "feat(analyst): editorial feedback cards (judul/info/bias/angle)"
```

---

### Task 9: Analyze Result container + shared section/card shells

**Files:**
- Create: `frontend/packages/features/src/analyst/result-shell.tsx` (shared `<ResultCard>`, `<Section>`, `<Kicker>`)
- Create: `frontend/packages/features/src/analyst/analyze-result.tsx`

**Interfaces:**
- Consumes: `UserNeedsRadar`, `UserNeedsBars`, `FeatureMatrix`, `FeedbackCards`, `orderedUserNeeds`, `groupedFeatures`.
- Produces: `<ResultCard kicker title? meta?>`, `<Section title>`, and `<AnalyzeResultCard title result={AnalyzeResult} />`.

- [ ] **Step 1: Implement the shared shell**

Create `frontend/packages/features/src/analyst/result-shell.tsx`:
```tsx
import type { ReactNode } from "react"

export function ResultCard({ kicker, meta, children }: { kicker: string; meta?: string; children: ReactNode }) {
  return (
    <div className="rounded-[10px] overflow-hidden" style={{ background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "var(--shadow-sm)" }}>
      <div className="flex items-center gap-2.5 px-4 py-2.5" style={{ borderBottom: "1px solid var(--line)" }}>
        <span className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.06em]" style={{ color: "var(--fg-muted)" }}>
          <span className="w-2 h-2 rounded-full" style={{ background: "linear-gradient(135deg, var(--accent), oklch(0.45 0.18 285))", boxShadow: "0 0 0 2px var(--accent-soft)" }} />
          {kicker}
        </span>
        {meta && <span className="ml-auto text-[11px]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>{meta}</span>}
      </div>
      {children}
    </div>
  )
}

export function Section({ title, accent, children, noBorder }: { title: ReactNode; accent?: ReactNode; children: ReactNode; noBorder?: boolean }) {
  return (
    <div className="p-4" style={noBorder ? undefined : { borderTop: "1px solid var(--line)" }}>
      <p className="text-[10.5px] font-semibold uppercase tracking-[0.06em] mb-3" style={{ color: "var(--fg-muted)" }}>{title}{accent}</p>
      {children}
    </div>
  )
}
```

- [ ] **Step 2: Implement the analyze result card**

Create `frontend/packages/features/src/analyst/analyze-result.tsx`:
```tsx
import type { AnalyzeResult } from "@ei-fe/api"
import { orderedUserNeeds, groupedFeatures } from "./data.js"
import { UserNeedsRadar } from "./user-needs-radar.js"
import { UserNeedsBars } from "./user-needs-bars.js"
import { FeatureMatrix } from "./feature-matrix.js"
import { FeedbackCards } from "./feedback-cards.js"
import { ResultCard, Section } from "./result-shell.js"

export function AnalyzeResultCard({ title, result }: { title: string; result: AnalyzeResult }) {
  const needs = orderedUserNeeds(result.user_needs)
  const detected = groupedFeatures(result.features).reduce((s, g) => s + g.detected, 0)

  return (
    <ResultCard kicker="Kartu Editorial" meta={`16 fitur · 6 kebutuhan`}>
      <div className="px-4 pt-3.5 pb-1">
        <div className="text-[10px] uppercase tracking-[0.06em]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>draf dianalisis</div>
        <h3 className="text-[18px] font-semibold leading-tight mt-1 mb-0" style={{ fontFamily: "var(--font-serif)" }}>{title}</h3>
      </div>

      <Section title="Kebutuhan Pembaca · sidik jari editorial">
        <div className="grid gap-4 items-center" style={{ gridTemplateColumns: "248px 1fr" }}>
          <div className="flex flex-col items-center gap-1">
            <UserNeedsRadar needs={needs} />
            <span className="text-[10px]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>bentuk = profil · angka di kanan</span>
          </div>
          <UserNeedsBars needs={needs} />
        </div>
      </Section>

      <Section title={<>16 Fitur Editorial · <span style={{ color: "var(--accent-fg)" }}>{detected} terdeteksi</span></>}>
        <FeatureMatrix features={result.features} />
      </Section>

      <Section title="Masukan Editorial">
        <FeedbackCards feedback={result.editorial_feedback} />
      </Section>
    </ResultCard>
  )
}
```

- [ ] **Step 3: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/result-shell.tsx frontend/packages/features/src/analyst/analyze-result.tsx
git commit -m "feat(analyst): analyze result card (radar + bars + matrix + feedback)"
```

---

### Task 10: Recommendation result (ranked bars + table + insights + summary)

**Files:**
- Create: `frontend/packages/features/src/analyst/ranked-bars.tsx`
- Create: `frontend/packages/features/src/analyst/recommendation-result.tsx`

**Interfaces:**
- Consumes: `RecommendationOutput` type, `activeFilters`, `inferNumericColumn` (Task 3), `ResultCard`/`Section` (Task 9).
- Produces: `<RankedBars rows valueCol labelCol />`, `<RecommendationResultCard result={RecommendationOutput} />`.

- [ ] **Step 1: Implement ranked bars**

Create `frontend/packages/features/src/analyst/ranked-bars.tsx`:
```tsx
export function RankedBars({ rows, valueCol, labelCol }: { rows: Record<string, unknown>[]; valueCol: string; labelCol: string }) {
  const max = rows.reduce((m, r) => Math.max(m, Number(r[valueCol]) || 0), 0) || 1
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((r, i) => {
        const v = Number(r[valueCol]) || 0
        return (
          <div key={i} className="flex flex-col gap-1">
            <div className="flex justify-between items-baseline gap-2.5">
              <span className="text-[12.5px]" style={{ color: "var(--fg)" }}>{String(r[labelCol] ?? "—")}</span>
              <span className="text-[11.5px] tabular-nums" style={{ fontFamily: "var(--font-mono)", color: "var(--fg)" }}>{v.toLocaleString("id-ID")}</span>
            </div>
            <div className="h-2 rounded-[3px] overflow-hidden" style={{ background: "var(--bg-sunken)" }}>
              <span className="block h-full rounded-[3px] transition-[width] duration-700" style={{ width: `${(v / max) * 100}%`, background: "var(--accent)" }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Implement the recommendation card**

Create `frontend/packages/features/src/analyst/recommendation-result.tsx`:
```tsx
import type { RecommendationOutput } from "@ei-fe/api"
import { activeFilters, inferNumericColumn, humanizeFilterKey } from "./data.js"
import { ResultCard, Section } from "./result-shell.js"
import { RankedBars } from "./ranked-bars.js"

export function RecommendationResultCard({ result }: { result: RecommendationOutput }) {
  const filters = activeFilters(result.filters_applied)
  const rows = result.sample_data
  const valueCol = inferNumericColumn(rows)
  const cols = rows.length ? Object.keys(rows[0]) : []
  const labelCol = cols.find((c) => typeof rows[0]?.[c] === "string") ?? cols[0] ?? ""

  return (
    <ResultCard kicker="Rekomendasi" meta={`data: ${result.data_source} · ${rows.length} baris`}>
      <Section title="Filter Diterapkan" noBorder>
        {filters.length ? (
          <div className="flex flex-wrap gap-1.5">
            {filters.map((f) => (
              <span key={f.key} className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-0.5 rounded-[5px]" style={{ fontFamily: "var(--font-mono)", background: "var(--bg-sunken)", border: "1px solid var(--line)", color: "var(--fg-muted)" }}>
                <span style={{ color: "var(--fg-faint)" }}>{f.label}</span><span style={{ color: "var(--fg)" }}>{f.value}</span>
              </span>
            ))}
          </div>
        ) : <span className="text-[12px]" style={{ color: "var(--fg-faint)" }}>Tanpa filter — semua data.</span>}
      </Section>

      {rows.length === 0 ? (
        <Section title="Data"><span className="text-[12px]" style={{ color: "var(--fg-faint)" }}>Tidak ada data untuk filter ini.</span></Section>
      ) : (
        <>
          {valueCol && (
            <Section title={`Teratas · ${humanizeFilterKey(valueCol)}`}>
              <RankedBars rows={rows} valueCol={valueCol} labelCol={labelCol} />
            </Section>
          )}
          <Section title="Data Mentah">
            <div className="overflow-x-auto rounded-[6px]" style={{ border: "1px solid var(--line)" }}>
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr>{cols.map((c) => (
                    <th key={c} className="text-left px-3 py-2 text-[9.5px] uppercase tracking-[0.05em] font-medium" style={{ color: "var(--fg-faint)", background: "var(--bg-sunken)", borderBottom: "1px solid var(--line)" }}>{humanizeFilterKey(c)}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>{cols.map((c) => {
                      const num = typeof r[c] === "number"
                      return <td key={c} className={`px-3 py-2 ${num ? "text-right tabular-nums" : ""}`} style={{ borderBottom: "1px solid var(--line)", fontFamily: num ? "var(--font-mono)" : undefined }}>{num ? (r[c] as number).toLocaleString("id-ID") : String(r[c] ?? "—")}</td>
                    })}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}

      {result.insights.length > 0 && (
        <Section title="Insight & Aksi">
          <div className="flex flex-col">
            {result.insights.map((ins, i) => (
              <div key={i} className="py-3" style={i > 0 ? { borderTop: "1px dashed var(--line)" } : undefined}>
                <p className="text-[13px] font-semibold mb-1" style={{ color: "var(--fg)" }}>{ins.title}</p>
                <p className="text-[12.5px] leading-relaxed m-0" style={{ color: "var(--fg-muted)" }}>{ins.insight}</p>
                <div className="flex gap-1.5 items-baseline mt-1.5">
                  <span className="text-[9px] uppercase tracking-[0.05em] px-1.5 py-0.5 rounded-[4px] shrink-0" style={{ fontFamily: "var(--font-mono)", color: "var(--accent-fg)", background: "var(--accent-soft)" }}>aksi</span>
                  <span className="text-[12.5px] leading-relaxed" style={{ color: "var(--fg)" }}>{ins.action}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Ringkasan">
        <p className="text-[14.5px] leading-relaxed m-0" style={{ fontFamily: "var(--font-serif)", color: "var(--fg)" }}>{result.summary}</p>
      </Section>
    </ResultCard>
  )
}
```

- [ ] **Step 3: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/ranked-bars.tsx frontend/packages/features/src/analyst/recommendation-result.tsx
git commit -m "feat(analyst): recommendation result (ranked bars + table + insights + summary)"
```

---

### Task 11: Message bubble + Composer

**Files:**
- Create: `frontend/packages/features/src/analyst/message-bubble.tsx`
- Create: `frontend/packages/features/src/analyst/composer.tsx`

**Interfaces:**
- Produces:
  - `<UserBubble command? text />`
  - `<Composer mode onModeChange onSubmit disabled />` where `mode: "analyze" | "recommendation"`, `onSubmit(payload)` is `{ kind: "analyze"; title: string; content: string } | { kind: "recommendation"; intent: string }`.

- [ ] **Step 1: Implement the message bubble**

Create `frontend/packages/features/src/analyst/message-bubble.tsx`:
```tsx
import { User } from "@ei-fe/ui"

export function UserBubble({ command, text }: { command?: string; text: string }) {
  return (
    <div className="flex gap-3 flex-row-reverse">
      <span className="w-7 h-7 rounded-[8px] grid place-items-center shrink-0 mt-0.5" style={{ background: "var(--fg)", color: "var(--bg-elev)" }}>
        <User size={15} />
      </span>
      <div className="rounded-[14px_14px_4px_14px] px-3.5 py-2.5 text-[13px] leading-normal max-w-[78%]" style={{ background: "var(--accent)", color: "white" }}>
        {command && <span className="block text-[11px] opacity-80 mb-0.5" style={{ fontFamily: "var(--font-mono)" }}>{command}</span>}
        <span className="whitespace-pre-wrap">{text}</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Implement the composer**

Create `frontend/packages/features/src/analyst/composer.tsx`:
```tsx
import { useState, type KeyboardEvent } from "react"
import { Sparkles, BarChart3, ArrowUp } from "@ei-fe/ui"

export type Mode = "analyze" | "recommendation"
export type SubmitPayload =
  | { kind: "analyze"; title: string; content: string }
  | { kind: "recommendation"; intent: string }

export function Composer({ mode, onModeChange, onSubmit, disabled }: {
  mode: Mode
  onModeChange: (m: Mode) => void
  onSubmit: (p: SubmitPayload) => void
  disabled: boolean
}) {
  const [text, setText] = useState("")
  const [error, setError] = useState<string | null>(null)

  function submit() {
    const value = text.trim()
    if (!value || disabled) return
    if (mode === "analyze") {
      const [firstLine, ...rest] = value.split("\n")
      const title = firstLine.trim().slice(0, 200)
      const content = (rest.join("\n").trim() || firstLine).slice(0, 20000)
      if (content.length < 1) { setError("Tempel isi draf untuk dianalisis."); return }
      onSubmit({ kind: "analyze", title: title || "Draf tanpa judul", content })
    } else {
      if (value.length < 3) { setError("Jelaskan yang ingin dianalisis (min. 3 karakter)."); return }
      onSubmit({ kind: "recommendation", intent: value.slice(0, 500) })
    }
    setText("")
    setError(null)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const modes: { id: Mode; label: string; Icon: typeof Sparkles }[] = [
    { id: "analyze", label: "Analisis Artikel", Icon: Sparkles },
    { id: "recommendation", label: "Rekomendasi", Icon: BarChart3 },
  ]

  return (
    <div>
      <div className="inline-flex gap-0.5 p-0.5 rounded-[8px] mb-2.5" style={{ background: "var(--bg-sunken)", border: "1px solid var(--line)" }}>
        {modes.map((m) => {
          const active = mode === m.id
          return (
            <button key={m.id} type="button" onClick={() => { onModeChange(m.id); setError(null) }}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] text-[12px]"
              style={active ? { background: "var(--bg-elev)", color: "var(--fg)", boxShadow: "var(--shadow-sm)", fontWeight: 500 } : { color: "var(--fg-muted)" }}>
              <m.Icon size={13} />{m.label}
            </button>
          )
        })}
      </div>
      <div className="flex items-end gap-2 p-2.5 rounded-[12px]" style={{ background: "var(--bg-elev)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-sm)" }}>
        <textarea
          value={text}
          onChange={(e) => { setText(e.target.value); if (error) setError(null) }}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder={mode === "analyze" ? "Tempel judul + isi draf untuk dianalisis…" : "Mis. artikel ekonomi paling banyak dibaca minggu ini…"}
          className="flex-1 resize-none bg-transparent border-0 outline-none text-[13px] leading-normal max-h-40"
          style={{ color: "var(--fg)" }}
        />
        <button type="button" onClick={submit} disabled={disabled || !text.trim()} aria-label="Kirim"
          className="w-8 h-8 rounded-[8px] grid place-items-center shrink-0 disabled:opacity-40"
          style={{ background: "var(--accent)", color: "white" }}>
          <ArrowUp size={16} />
        </button>
      </div>
      {error && <p className="text-[11.5px] mt-1.5" role="alert" style={{ color: "var(--bad)" }}>{error}</p>}
      <p className="text-center text-[10.5px] mt-2" style={{ color: "var(--fg-faint)" }}>AI Analyst memberi masukan editorial dari fitur konten &amp; data performa historis.</p>
    </div>
  )
}
```

- [ ] **Step 3: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/message-bubble.tsx frontend/packages/features/src/analyst/composer.tsx
git commit -m "feat(analyst): composer (mode switch + validation) and user bubble"
```

---

### Task 12: Analyst view (thread orchestration) + feature index

**Files:**
- Create: `frontend/packages/features/src/analyst/analyst-view.tsx`
- Create: `frontend/packages/features/src/analyst/index.ts`
- Modify: `frontend/packages/features/src/index.ts` (re-export)

**Interfaces:**
- Consumes: `useAnalyzeArticle`, `useRecommendation` (Task 2); `UserBubble`, `Composer`, `AnalyzeResultCard`, `RecommendationResultCard`; icons `Bot`, `Sparkles`, `Plus`.
- Produces: `<AnalystView initialTitle? initialMode? />`, exported via `@ei-fe/features`.

- [ ] **Step 1: Implement the view**

Create `frontend/packages/features/src/analyst/analyst-view.tsx`:
```tsx
import { useState, useRef, useEffect } from "react"
import { isApiError } from "@ei-fe/core"
import { useAnalyzeArticle, useRecommendation } from "@ei-fe/api"
import type { AnalyzeResult, RecommendationOutput } from "@ei-fe/api"
import { Bot, Sparkles, Plus } from "@ei-fe/ui"
import { UserBubble } from "./message-bubble.js"
import { Composer, type Mode, type SubmitPayload } from "./composer.js"
import { AnalyzeResultCard } from "./analyze-result.js"
import { RecommendationResultCard } from "./recommendation-result.js"

type Msg =
  | { id: string; role: "user"; command: string; text: string }
  | { id: string; role: "analyze"; title: string; data: AnalyzeResult }
  | { id: string; role: "reco"; data: RecommendationOutput }
  | { id: string; role: "error"; text: string }
  | { id: string; role: "loading" }

let seq = 0
const nextId = () => `m${seq++}`

const SUGGESTIONS = [
  { mode: "analyze" as Mode, title: "Analisis draf", text: "Tempel judul + isi artikel untuk skor 16 fitur, kebutuhan pembaca, dan masukan editorial." },
  { mode: "recommendation" as Mode, title: "Performa minggu ini", text: "Artikel ekonomi paling banyak dibaca minggu ini, dan apa yang harus ditulis berikutnya?" },
]

export function AnalystView({ initialTitle, initialMode }: { initialTitle?: string; initialMode?: Mode }) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [mode, setMode] = useState<Mode>(initialMode ?? "analyze")
  const scrollRef = useRef<HTMLDivElement>(null)
  const analyze = useAnalyzeArticle()
  const reco = useRecommendation()
  const busy = analyze.isPending || reco.isPending

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  function push(m: Omit<Msg, "id">) { setMessages((p) => [...p, { ...m, id: nextId() } as Msg]) }
  function replaceLoading(m: Omit<Msg, "id">) {
    setMessages((p) => { const out = p.filter((x) => x.role !== "loading"); return [...out, { ...m, id: nextId() } as Msg] })
  }

  async function handleSubmit(p: SubmitPayload) {
    if (p.kind === "analyze") {
      push({ role: "user", command: "/analyze · draf artikel", text: p.title })
      push({ role: "loading" })
      try {
        const data = await analyze.mutateAsync({ title: p.title, content: p.content })
        replaceLoading({ role: "analyze", title: p.title, data })
      } catch (e) {
        replaceLoading({ role: "error", text: isApiError(e) ? e.message : "Analisis gagal. Coba lagi." })
      }
    } else {
      push({ role: "user", command: "/recommendation", text: p.intent })
      push({ role: "loading" })
      try {
        const data = await reco.mutateAsync(p.intent)
        replaceLoading({ role: "reco", data })
      } catch (e) {
        replaceLoading({ role: "error", text: isApiError(e) ? e.message : "Rekomendasi gagal. Coba lagi." })
      }
    }
  }

  const empty = messages.length === 0

  return (
    <div className="flex flex-col min-h-0 flex-1" style={{ background: "var(--bg)" }}>
      <header className="flex items-center gap-3 px-7 py-4" style={{ borderBottom: "1px solid var(--line)", background: "var(--bg-elev)" }}>
        <span className="w-[34px] h-[34px] rounded-[9px] grid place-items-center shrink-0" style={{ background: "linear-gradient(135deg, var(--accent), oklch(0.45 0.18 285))", color: "white" }}><Sparkles size={17} /></span>
        <div>
          <div className="text-[15px] font-semibold tracking-tight">AI Analyst</div>
          <div className="text-[11.5px]" style={{ color: "var(--fg-muted)" }}>Asisten redaksi · analisis draf &amp; rekomendasi performa</div>
        </div>
        <span className="flex-1" />
        {!empty && (
          <button onClick={() => setMessages([])} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[6px] text-[12.5px]" style={{ color: "var(--fg-muted)", border: "1px solid var(--line)" }}>
            <Plus size={14} /> Analisis baru
          </button>
        )}
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[860px] px-6 py-7 flex flex-col gap-6">
          {empty ? (
            <div className="flex flex-col items-center gap-6 py-10 text-center">
              <span className="w-14 h-14 rounded-[16px] grid place-items-center" style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}><Sparkles size={26} /></span>
              <div>
                <h2 className="text-[20px] font-semibold tracking-tight m-0">Apa yang bisa saya bantu?</h2>
                <p className="text-[13px] mt-1.5 m-0" style={{ color: "var(--fg-muted)" }}>Analisis draf sebelum terbit, atau minta rekomendasi dari data performa.</p>
              </div>
              <div className="grid gap-3 w-full max-w-xl" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                {SUGGESTIONS.map((s) => (
                  <button key={s.title} onClick={() => setMode(s.mode)} className="text-left rounded-[10px] p-3.5" style={{ background: "var(--bg-elev)", border: "1px solid var(--line)" }}>
                    <span className="block text-[13px] font-medium">{s.title}</span>
                    <span className="block text-[12px] mt-1" style={{ color: "var(--fg-muted)" }}>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => {
              if (m.role === "user") return <UserBubble key={m.id} command={m.command} text={m.text} />
              if (m.role === "loading") return <BotRow key={m.id}><LoadingDots /></BotRow>
              if (m.role === "error") return <BotRow key={m.id}><div className="text-[13px] px-3.5 py-2.5 rounded-[10px]" style={{ background: "var(--bad-soft)", color: "var(--bad)", border: "1px solid oklch(0.58 0.18 25 / 0.25)" }}>{m.text}</div></BotRow>
              if (m.role === "analyze") return <BotRow key={m.id}><AnalyzeResultCard title={m.title} result={m.data} /></BotRow>
              return <BotRow key={m.id}><RecommendationResultCard result={m.data} /></BotRow>
            })
          )}
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--line)", background: "var(--bg-elev)" }}>
        <div className="mx-auto max-w-[860px] px-6 py-3.5">
          <Composer mode={mode} onModeChange={setMode} onSubmit={handleSubmit} disabled={busy} />
        </div>
      </div>
    </div>
  )
}

function BotRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="w-7 h-7 rounded-[8px] grid place-items-center shrink-0 mt-0.5" style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}><Bot size={15} /></span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  )
}

function LoadingDots() {
  return (
    <div className="inline-flex items-center gap-1.5 px-3.5 py-3 rounded-[10px]" style={{ background: "var(--bg-sunken)" }}>
      {[0, 1, 2].map((i) => (
        <span key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--fg-ghost)", animation: `analystPulse 1.2s ${i * 0.15}s infinite ease-in-out` }} />
      ))}
    </div>
  )
}
```

Note: `initialTitle` prefill (Task 14) is consumed via a small effect — add when wiring contextual entry; the prop is declared now to lock the interface.

- [ ] **Step 2: Add the loading keyframe to globals.css**

Append to `frontend/packages/app/src/styles/globals.css` (a new keyframe, not a legacy component class — allowed):
```css
@keyframes analystPulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  [style*="analystPulse"] { animation: none !important; opacity: 0.6 !important; }
}
```

- [ ] **Step 3: Verify `isApiError` exists; if not, use instanceof**

Run: `grep -rn "isApiError\|class ApiError" frontend/packages/core/src`
If `isApiError` is not exported, replace `isApiError(e)` with `e instanceof ApiError` and import `ApiError` from `@ei-fe/core` (it is exported — see `client.ts`). Adjust the import line accordingly.

- [ ] **Step 4: Feature index exports**

Create `frontend/packages/features/src/analyst/index.ts`:
```ts
export { AnalystView } from "./analyst-view.js"
export type { Mode } from "./composer.js"
```
Add to `frontend/packages/features/src/index.ts`:
```ts
export { AnalystView } from "./analyst/index.js"
```

- [ ] **Step 5: Typecheck & commit**

```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/ frontend/packages/features/src/index.ts frontend/packages/app/src/styles/globals.css
git commit -m "feat(analyst): conversational thread view + feature exports"
```

---

### Task 13: Route, sidebar nav, app wiring, and demo mocks

**Files:**
- Create: `frontend/packages/app/src/routes/analyst.tsx`
- Modify: `frontend/packages/app/src/app.tsx`
- Modify: `frontend/packages/ui/src/layout/sidebar.tsx`
- Modify: `frontend/packages/app/src/mocks/handlers.ts`
- Create: `frontend/packages/app/src/mocks/fixtures/analyst-analyze.json`, `analyst-recommendation.json`

**Interfaces:**
- Consumes: `AnalystView` (Task 12).
- Produces: reachable route `/analyst`; functional MSW mocks for the two endpoints.

- [ ] **Step 1: Route**

Create `frontend/packages/app/src/routes/analyst.tsx`:
```tsx
import { AnalystView } from "@ei-fe/features"

export function AnalystRoute() {
  return <AnalystView />
}
```

- [ ] **Step 2: Wire the route**

In `frontend/packages/app/src/app.tsx`: import `{ AnalystRoute } from "./routes/analyst.js"` and add child route `{ path: "analyst", element: <AnalystRoute /> }`.

- [ ] **Step 3: Sidebar nav**

In `frontend/packages/ui/src/layout/sidebar.tsx`, add to `EDITORIAL_NAV`:
```ts
{ to: "/morning", label: "Morning Brief" },
{ to: "/article", label: "Artikel" },
{ to: "/analyst", label: "AI Analyst" },
```

- [ ] **Step 4: Mock fixtures**

Create `frontend/packages/app/src/mocks/fixtures/analyst-analyze.json` with a realistic `AnalyzeResult` (16 features w/ status+reasoning, 6 user_needs with scores like Educate 88 / Perspective 72, editorial_feedback lists). Create `analyst-recommendation.json` with a realistic `RecommendationOutput` (5 sample_data rows incl. `page_views`, 3 insights, summary, `data_source: "airflow_json"`). Use the content from the approved mockup (`scratchpad/analyst-mockup.html`) as the source of truth for values.

- [ ] **Step 5: Mock handlers**

In `frontend/packages/app/src/mocks/handlers.ts`, import the two fixtures and add:
```ts
http.post(`${BASE}/analyst/analyze`, () => HttpResponse.json(analystAnalyze)),
http.post(`${BASE}/analyst/recommendation`, () => HttpResponse.json(analystRecommendation)),
```

- [ ] **Step 6: Visual verification (the real gate for all UI tasks)**

Run the app with mocks and screenshot:
```bash
cd frontend && VITE_MOCK=true bun run dev
```
Then drive Playwright (or a browser) to `http://localhost:5173/analyst`:
- Empty state shows welcome + 2 suggestion cards.
- Submit in "Analisis Artikel" mode → loading dots → analyze card with radar (Edukasi/Perspektif dominant), feature matrix (detected flags lit + reasoning), 4 feedback cards.
- Switch to "Rekomendasi" → submit → ranked bars + table + insight cards + serif summary.
- Confirm no horizontal page scroll; radar labels not clipped; tokens/fonts match the rest of the app.
- Toggle OS reduced-motion → animations settle to final state.

Fix any visual issues before committing.

- [ ] **Step 7: Commit**

```bash
git add frontend/packages/app/src/routes/analyst.tsx frontend/packages/app/src/app.tsx frontend/packages/ui/src/layout/sidebar.tsx frontend/packages/app/src/mocks/
git commit -m "feat(app): mount AI Analyst route, sidebar entry, and demo mocks"
```

---

### Task 14: Contextual "Analisis draf" entry point

**Files:**
- Modify: `frontend/packages/features/src/analyst/analyst-view.tsx` (consume `initialTitle`/`initialMode`)
- Modify: `frontend/packages/app/src/routes/analyst.tsx` (read router state / query param)
- Modify: `frontend/packages/features/src/cluster-detail/cluster-header.tsx` (add the action button)

**Interfaces:**
- Consumes: React Router `useLocation`/`useSearchParams`.
- Produces: a button on the cluster header that navigates to `/analyst` in analyze mode with the cluster label prefilled into the composer's first line.

- [ ] **Step 1: Prefill support in the view**

In `analyst-view.tsx`, the `Composer` gains an optional `initialText` prop (add it: `initialText?: string` used as the textarea's initial state). Pass `initialTitle` through `AnalystView` → `Composer initialText={initialTitle}` and set `initialMode`. (Adjust `Composer` to seed `useState(initialText ?? "")`.)

- [ ] **Step 2: Route reads context**

In `routes/analyst.tsx`:
```tsx
import { useSearchParams } from "react-router-dom"
import { AnalystView } from "@ei-fe/features"

export function AnalystRoute() {
  const [params] = useSearchParams()
  const title = params.get("title") ?? undefined
  return <AnalystView initialTitle={title} initialMode={title ? "analyze" : undefined} />
}
```

- [ ] **Step 3: Cluster header button**

In `cluster-header.tsx`, add a button that does `navigate(\`/analyst?title=${encodeURIComponent(label)}\`)` with label "Analisis draf", styled as a ghost button consistent with existing actions. Only show when a label exists.

- [ ] **Step 4: Verify & commit**

Visually verify: from a cluster detail page, "Analisis draf" navigates to the Analyst with the title prefilled in analyze mode.
```bash
cd frontend && bun run build
git add frontend/packages/features/src/analyst/ frontend/packages/app/src/routes/analyst.tsx frontend/packages/features/src/cluster-detail/cluster-header.tsx
git commit -m "feat(analyst): contextual 'Analisis draf' entry from cluster detail"
```

---

### Task 15: Morning Brief polish — shared KPI primitive

**Files:**
- Create: `frontend/packages/ui/src/primitives/kpi.tsx`
- Modify: `frontend/packages/ui/src/index.ts` (export `Kpi`)
- Modify: `frontend/packages/features/src/morning/morning-view.tsx` (use `Kpi`)

**Interfaces:**
- Produces: `<Kpi label value sub? />` shared primitive (Tailwind + tokens, no legacy `.kpi` class).

- [ ] **Step 1: Implement the primitive**

Create `frontend/packages/ui/src/primitives/kpi.tsx`:
```tsx
import type { ReactNode } from "react"

export function Kpi({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-[10px] p-4" style={{ background: "var(--bg-elev)", border: "1px solid var(--line)" }}>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.06em] font-medium" style={{ color: "var(--fg-faint)" }}>{label}</div>
      <div className="flex items-baseline gap-2 mt-1.5 text-[26px] font-medium tracking-tight tabular-nums">{value}</div>
      {sub && <div className="text-[11px] mt-1" style={{ color: "var(--fg-muted)" }}>{sub}</div>}
    </div>
  )
}
```

- [ ] **Step 2: Export & adopt**

Export `Kpi` from `frontend/packages/ui/src/index.ts`. In `morning-view.tsx`, replace the `KpiRow` inner markup (the four `.kpi`/`.kpi-label`/`.kpi-value` blocks) with `<Kpi label=… value=… />`, keeping the `grid grid-4` container or replacing it with a Tailwind grid `style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}`.

- [ ] **Step 3: Verify & commit**

Visually verify the Morning Brief KPI row is unchanged in look (or improved) and uses no `.kpi` legacy class.
```bash
cd frontend && bun run build
git add frontend/packages/ui/src/primitives/kpi.tsx frontend/packages/ui/src/index.ts frontend/packages/features/src/morning/morning-view.tsx
git commit -m "feat(morning): shared Kpi primitive, drop legacy .kpi classes"
```

---

### Task 16: Final verification

- [ ] **Step 1: Full build + unit tests**

```bash
cd frontend && bun run build && bun test && bun run lint
```
Expected: build OK, all unit tests pass (api schemas + analyst data), lint clean.

- [ ] **Step 2: End-to-end visual pass (mocks)**

`VITE_MOCK=true bun run dev`; walk the full Analyst flow + Morning Brief + contextual entry per Task 13 Step 6. Capture before/after screenshots.

- [ ] **Step 3: Update docs**

If any top-level dep was unexpectedly required, update `docs/tech-stack.md` (should be none). Note the new `/analyst` route in any frontend route inventory if one exists (`docs/frontend.md`).

```bash
git add -A && git commit -m "docs(analyst): note AI Analyst route" # only if docs changed
```

---

## Self-review notes (coverage)

- Spec §4 layout → Tasks 1–15 map 1:1 to the file list.
- Spec §5 API → Tasks 1–2.
- Spec §6 viz → Tasks 5 (radar), 6 (bars), 7 (matrix), 10 (ranked bars/table).
- Spec §7 composer/thread → Tasks 11–12.
- Spec §8 contextual → Task 14.
- Spec §9 Morning Brief → Task 15.
- Spec §10 testing → pure-logic tests in Tasks 1, 3; visual verification in Tasks 13, 16 (adjusted to codebase reality: no React render-test infra).
- Spec §11 risks → score normalization (Task 3 `orderedUserNeeds`), dynamic `sample_data` (`inferNumericColumn` + table fallback), filter humanization (`activeFilters`), demo mocks (Task 13).
