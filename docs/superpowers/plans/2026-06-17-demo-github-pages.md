# GitHub Pages Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully offline GitHub Pages demo of the content intelligence dashboard using the existing React app with MSW mock data.

**Architecture:** Activate MSW in production builds via `VITE_MOCK=true`; enrich fixture JSON with insight fields and quadrant data; deploy `dist/` to GitHub Pages via Actions. No backend changes needed.

**Tech Stack:** Vite, React, MSW v2, bun, GitHub Actions, `peaceiris/actions-gh-pages`

---

## File Map

| File | Change |
|------|--------|
| `frontend/packages/app/src/main.tsx` | Enable MSW when `VITE_MOCK=true` |
| `frontend/packages/app/vite.config.ts` | Add `base` env var |
| `frontend/packages/app/src/mocks/handlers.ts` | Fix cluster-run response; add quadrant-summary + quadrant/:quadrant handlers; update cluster/:id to use details map |
| `frontend/packages/api/tests/mocks/fixtures/morning-clusters.json` | Add `demand_score`, `high_demand`, `performance_level`, `editorial_quadrant`, `bullet_insights`; fill insight fields for top 5; update `tempo_covered` for winning/evergreen/too_early clusters |
| `frontend/packages/api/tests/mocks/fixtures/cluster-detail.json` | Fill `what_happened`, `parties_involved`, `editorial_angle`, `bullet_insights`; add `parent_cluster: null`, `sibling_clusters: null`; expand members to 12 |
| `frontend/packages/api/tests/mocks/fixtures/cluster-details-map.json` | New — rich detail for clusters 2–5 (Sidang MK, Korupsi, PPRT, Prabowo) |
| `frontend/packages/api/tests/schemas.test.ts` | Add fixture schema validation tests |
| `.github/workflows/demo.yml` | New — build + deploy workflow |

---

## Task 1: Enable VITE_MOCK build flag

**Files:**
- Modify: `frontend/packages/app/src/main.tsx:8`
- Modify: `frontend/packages/app/vite.config.ts`

- [ ] **Step 1: Update MSW bootstrap condition in main.tsx**

  Current line 8:
  ```ts
  if (import.meta.env.DEV && import.meta.env["VITE_ENABLE_MOCK"] !== "false") {
  ```

  Replace with:
  ```ts
  if (import.meta.env.DEV || import.meta.env["VITE_MOCK"] === "true") {
  ```

  This makes MSW activate in dev (existing behaviour) AND in any build where `VITE_MOCK=true` is set.

- [ ] **Step 2: Add base URL support in vite.config.ts**

  Replace the full `vite.config.ts` content:
  ```ts
  import { defineConfig } from "vite"
  import react from "@vitejs/plugin-react"
  import tailwindcss from "@tailwindcss/vite"
  import path from "path"

  export default defineConfig({
    plugins: [react(), tailwindcss()],
    base: process.env["VITE_BASE"] ?? "/",
    resolve: {
      alias: {
        "@ei-fe/core": path.resolve(__dirname, "../core/src"),
        "@ei-fe/api": path.resolve(__dirname, "../api/src"),
        "@ei-fe/ui": path.resolve(__dirname, "../ui/src"),
        "@ei-fe/features": path.resolve(__dirname, "../features/src"),
      },
    },
    build: {
      target: "es2022",
    },
    server: {
      watch: {
        usePolling: true,
        interval: 300,
      },
      proxy: {
        "/api/v1": {
          target: process.env["VITE_BACKEND_URL"] ?? "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  })
  ```

- [ ] **Step 3: Verify mock build produces output**

  Run from `frontend/packages/app/`:
  ```bash
  VITE_MOCK=true VITE_BASE=/content-intelligence/ bun run build
  ```

  Expected: build completes without errors, `dist/` folder is created.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/packages/app/src/main.tsx frontend/packages/app/vite.config.ts
  git commit -m "feat(demo): enable VITE_MOCK build flag for GitHub Pages demo"
  ```

---

## Task 2: Fix mock handlers — cluster run + quadrant endpoints

**Files:**
- Modify: `frontend/packages/app/src/mocks/handlers.ts`

The cluster run handler is missing the required `stages` field from `ClusterRunSchema`. Also add the two quadrant endpoints that the Opportunity Matrix needs.

- [ ] **Step 1: Fix cluster run handler + add quadrant handlers**

  Open `handlers.ts`. Make three changes:

  **Fix 1** — add `stages: []` to the cluster run response (around line 135):
  ```ts
  http.get(`${BASE}/clusters/runs/latest`, () =>
    HttpResponse.json({
      id: "a1b2c3d4-run1-4000-8000-000000000001",
      algorithm: "hdbscan",
      algorithm_version: "0.8.33",
      params: { min_cluster_size: 5, min_samples: 3, metric: "euclidean" },
      started_at: new Date(Date.now() - 3_600_000).toISOString(),
      finished_at: new Date(Date.now() - 2_700_000).toISOString(),
      notes: null,
      cluster_count: morningClusters.clusters.length,
      has_insights: true,
      stages: [],
    }),
  ),
  ```

  **Fix 2** — add quadrant handlers after the `clusters/runs/latest` handler:
  ```ts
  http.get(`${BASE}/clusters/quadrant-summary`, () => {
    const counts = { opportunity: 0, winning: 0, evergreen: 0, ignore: 0, too_early: 0, total: 0 }
    for (const c of morningClusters.clusters) {
      const q = c.editorial_quadrant as keyof typeof counts | null
      if (q && q in counts && q !== "total") {
        counts[q]++
        counts.total++
      }
    }
    return HttpResponse.json(counts)
  }),
  http.get(`${BASE}/clusters/quadrant/:quadrant`, ({ params, request }) => {
    const { quadrant } = params as { quadrant: string }
    const url = new URL(request.url)
    const limit = parseInt(url.searchParams.get("limit") ?? "8", 10)
    const filtered = morningClusters.clusters
      .filter((c) => c.editorial_quadrant === quadrant)
      .slice(0, limit)
    return HttpResponse.json({
      clusters: filtered,
      served_at: morningClusters.served_at,
      is_stale: morningClusters.is_stale,
      max_age_hours: morningClusters.max_age_hours,
    })
  }),
  ```

- [ ] **Step 2: Verify dev server serves quadrant endpoints**

  Run dev server:
  ```bash
  cd frontend && bun run dev
  ```

  In browser DevTools → Network, navigate to Morning view. Confirm `GET /api/v1/clusters/quadrant-summary` returns a 200 with JSON like `{"opportunity":3,"winning":2,"evergreen":1,"ignore":3,"too_early":1,"total":10}`.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/packages/app/src/mocks/handlers.ts
  git commit -m "feat(demo): fix cluster run stages field; add quadrant mock handlers"
  ```

---

## Task 3: Enrich morning-clusters.json

**Files:**
- Modify: `frontend/packages/api/tests/mocks/fixtures/morning-clusters.json`

Add `demand_score`, `high_demand`, `performance_level`, `editorial_quadrant`, `bullet_insights` to all clusters. Fill in `what_happened`, `parties_involved`, `editorial_angle` for top 5. Update `tempo_covered`/`last_internal_days_ago` for winning/evergreen/too_early clusters.

- [ ] **Step 1: Replace morning-clusters.json with enriched version**

  Write the complete file:
  ```json
  {
    "clusters": [
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000001",
        "label": "Kenaikan Harga BBM Pertamina",
        "member_count": 23,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.875,
        "competitor_count": 8,
        "trend_match_count": 3,
        "tempo_covered": false,
        "last_internal_days_ago": null,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.91,
        "competitor_freshness_days": 1,
        "demand_score": 0.95,
        "high_demand": true,
        "performance_level": "low",
        "editorial_quadrant": "opportunity",
        "what_happened": "Pertamina menaikkan harga BBM non-subsidi Pertamax, Dexlite, dan Pertamina Dex mulai 1 Mei 2025, dipicu pelemahan rupiah dan lonjakan harga minyak dunia ke level $94/barel.",
        "parties_involved": ["Pertamina", "DPR RI Komisi VII", "Asosiasi Pengusaha Logistik", "LPEM UI"],
        "editorial_angle": "Investigasi: apakah Pertamina melakukan kajian dampak inflasi sebelum menaikkan harga? Minta dokumen RKAP 2025 dan bandingkan proyeksi dampak inflasi BI vs kenaikan aktual.",
        "bullet_insights": ["8 kompetitor sudah menulis, Tempo belum hadir", "3 keyword trend aktif minggu ini", "Topik konsumsi publik luas — potensi trafik tinggi"],
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000002",
        "label": "Sidang MK Sengketa Pilkada Kaltim",
        "member_count": 18,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.712,
        "competitor_count": 6,
        "trend_match_count": 2,
        "tempo_covered": false,
        "last_internal_days_ago": null,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.78,
        "competitor_freshness_days": 2,
        "demand_score": 0.82,
        "high_demand": true,
        "performance_level": "low",
        "editorial_quadrant": "opportunity",
        "what_happened": "MK menyidangkan sengketa hasil Pilkada Kaltim 2024 yang diajukan pasangan calon kalah, dengan potensi putusan dalam dua minggu ke depan.",
        "parties_involved": ["Mahkamah Konstitusi", "Pasangan Calon Kaltim", "KPU Kaltim", "Bawaslu"],
        "editorial_angle": "Liputan langsung sidang MK: fokus pada kualitas bukti yang diajukan dan kemungkinan preseden putusan untuk sengketa pilkada serupa di daerah lain.",
        "bullet_insights": ["6 kompetitor aktif meliput, Tempo belum", "Deadline putusan menciptakan urgensi editorial", "2 keyword trend terkait aktif"],
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000003",
        "label": "Korupsi Dana Desa Jawa Tengah",
        "member_count": 31,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.68,
        "competitor_count": 5,
        "trend_match_count": 2,
        "tempo_covered": true,
        "last_internal_days_ago": 3,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.71,
        "competitor_freshness_days": 2,
        "demand_score": 0.75,
        "high_demand": true,
        "performance_level": "high",
        "editorial_quadrant": "winning",
        "what_happened": "Kejaksaan Tinggi Jawa Tengah menetapkan 12 kepala desa sebagai tersangka korupsi dana desa senilai Rp 4,8 miliar di 3 kabupaten melalui proyek fiktif dan markup material.",
        "parties_involved": ["Kejati Jawa Tengah", "12 Kepala Desa", "Kemendesa", "BPK"],
        "editorial_angle": "Analisis pola: apakah ada distributor rekanan yang sama di ketiga kabupaten? Bandingkan modus dengan kasus korupsi dana desa di Jatim dan NTB — cari pola sistemik.",
        "bullet_insights": ["Tempo sudah meliput 3 hari lalu dengan trafik bagus", "5 kompetitor aktif — butuh angle investigatif untuk membedakan", "BPK temukan pola serupa di 5 provinsi lain"],
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000004",
        "label": "Pengesahan RUU PPRT DPR",
        "member_count": 12,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.615,
        "competitor_count": 4,
        "trend_match_count": 1,
        "tempo_covered": true,
        "last_internal_days_ago": null,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.63,
        "competitor_freshness_days": 1,
        "demand_score": 0.68,
        "high_demand": true,
        "performance_level": null,
        "editorial_quadrant": "too_early",
        "what_happened": "DPR memasukkan RUU Perlindungan Pekerja Rumah Tangga ke Prolegnas 2025, 12 tahun setelah pertama kali diajukan pada 2012.",
        "parties_involved": ["DPR RI Baleg", "Jaringan Nasional Advokasi PRT", "ILO", "Komnas HAM"],
        "editorial_angle": "Follow-up langsung ke Baleg DPR: siapa fraksi yang masih menghambat, dan perubahan apa dari draf 2012 yang membuat RUU ini berbeda kali ini?",
        "bullet_insights": ["Artikel Tempo terlalu baru — GSC butuh 1–3 hari", "Pantau besok untuk melihat trafik awal", "4 kompetitor sudah menulis angle serupa"],
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000005",
        "label": "Prabowo-Xi Jinping Bilateral Bali",
        "member_count": 9,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.548,
        "competitor_count": 7,
        "trend_match_count": 2,
        "tempo_covered": false,
        "last_internal_days_ago": null,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.59,
        "competitor_freshness_days": 1,
        "demand_score": 0.61,
        "high_demand": true,
        "performance_level": "low",
        "editorial_quadrant": "opportunity",
        "what_happened": "Presiden Prabowo bertemu Xi Jinping di sela G20 Bali, menghasilkan komitmen investasi senilai $8,5 miliar di sektor infrastruktur dan transisi energi.",
        "parties_involved": ["Prabowo Subianto", "Xi Jinping", "Kementerian Investasi", "BKPM"],
        "editorial_angle": "Analisis konkret: bandingkan $8,5 miliar dengan realisasi janji investasi China era Jokowi — berapa yang benar-benar masuk vs tertahan sebagai komitmen di atas kertas.",
        "bullet_insights": ["7 kompetitor menulis, Tempo belum hadir", "Angle komparatif era Jokowi vs Prabowo belum disentuh kompetitor", "2 keyword trend aktif terkait G20 Bali"],
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000006",
        "label": "BPJS Kesehatan Iuran Kelas Baru",
        "member_count": 15,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.483,
        "competitor_count": 3,
        "trend_match_count": 1,
        "tempo_covered": true,
        "last_internal_days_ago": 2,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.51,
        "competitor_freshness_days": 3,
        "demand_score": 0.52,
        "high_demand": true,
        "performance_level": "high",
        "editorial_quadrant": "winning",
        "what_happened": "BPJS Kesehatan umumkan struktur iuran kelas baru (KRIS) per Juli 2025 dengan penggabungan kelas 1 dan 2 menjadi satu tarif standar Rp 150.000/bulan.",
        "parties_involved": ["BPJS Kesehatan", "Kemenkes", "DPR Komisi IX", "IDI"],
        "editorial_angle": "Kalkulasi dampak ke peserta mandiri: hitung selisih iuran kelas baru vs kelas lama untuk berbagai segmen pendapatan dan tunjukkan siapa yang diuntungkan vs dirugikan.",
        "bullet_insights": ["Artikel Tempo aktif mendapat trafik organik", "3 kompetitor menulis — butuh angle kalkulasi yang lebih tajam", "Berpotensi diperbarui menjelang Juli 2025"],
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000007",
        "label": "Kebakaran Hutan Kalimantan Barat",
        "member_count": 7,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.441,
        "competitor_count": 4,
        "trend_match_count": 2,
        "tempo_covered": false,
        "last_internal_days_ago": null,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.45,
        "competitor_freshness_days": 4,
        "demand_score": 0.38,
        "high_demand": false,
        "performance_level": "low",
        "editorial_quadrant": "ignore",
        "what_happened": null,
        "parties_involved": null,
        "editorial_angle": null,
        "bullet_insights": null,
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000008",
        "label": "Startup Teknologi PHK Gelombang Kedua",
        "member_count": 20,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.396,
        "competitor_count": 6,
        "trend_match_count": 0,
        "tempo_covered": true,
        "last_internal_days_ago": 1,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.39,
        "competitor_freshness_days": 5,
        "demand_score": 0.31,
        "high_demand": false,
        "performance_level": "high",
        "editorial_quadrant": "evergreen",
        "what_happened": null,
        "parties_involved": null,
        "editorial_angle": null,
        "bullet_insights": null,
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000009",
        "label": "Rupiah Melemah Terhadap Dolar AS",
        "member_count": 11,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.352,
        "competitor_count": 5,
        "trend_match_count": 1,
        "tempo_covered": false,
        "last_internal_days_ago": null,
        "underperformed": true,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.34,
        "competitor_freshness_days": 3,
        "demand_score": 0.28,
        "high_demand": false,
        "performance_level": "low",
        "editorial_quadrant": "ignore",
        "what_happened": null,
        "parties_involved": null,
        "editorial_angle": null,
        "bullet_insights": null,
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      },
      {
        "id": "a1b2c3d4-0001-4000-8000-000000000010",
        "label": "Seleksi CPNS 2025 Kemenpan RB",
        "member_count": 8,
        "is_current": true,
        "created_at": "2026-05-09T06:00:00Z",
        "trend_velocity": 0.299,
        "competitor_count": 2,
        "trend_match_count": 1,
        "tempo_covered": false,
        "last_internal_days_ago": null,
        "underperformed": false,
        "parent_cluster_id": null,
        "weighted_trend_score": 0.28,
        "competitor_freshness_days": 6,
        "demand_score": 0.22,
        "high_demand": false,
        "performance_level": "low",
        "editorial_quadrant": "ignore",
        "what_happened": null,
        "parties_involved": null,
        "editorial_angle": null,
        "bullet_insights": null,
        "insight_calculated_at": "2026-05-09T06:05:00Z"
      }
    ],
    "served_at": "2026-05-09T06:05:00Z",
    "is_stale": false,
    "max_age_hours": 36
  }
  ```

- [ ] **Step 2: Verify quadrant-summary now returns correct counts**

  With dev server running, navigate to Morning view. The Opportunity Matrix should show: 🔥 3, ✅ 2, ⏳ 1, 🪦 1, 💤 3.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/packages/api/tests/mocks/fixtures/morning-clusters.json
  git commit -m "feat(demo): enrich morning-clusters with quadrant + insight fields"
  ```

---

## Task 4: Enrich cluster-detail.json (BBM cluster)

**Files:**
- Modify: `frontend/packages/api/tests/mocks/fixtures/cluster-detail.json`

Add missing schema fields (`parent_cluster`, `sibling_clusters`, `high_demand`, `performance_level`, `editorial_quadrant`, `bullet_insights`), fill insight fields, expand to 12 members.

- [ ] **Step 1: Replace cluster-detail.json with enriched version**

  ```json
  {
    "id": "a1b2c3d4-0001-4000-8000-000000000001",
    "label": "Kenaikan Harga BBM Pertamina",
    "member_count": 23,
    "is_current": true,
    "created_at": "2026-05-09T06:00:00Z",
    "trend_velocity": 0.875,
    "competitor_count": 8,
    "trend_match_count": 3,
    "tempo_covered": false,
    "last_internal_days_ago": null,
    "underperformed": false,
    "parent_cluster_id": null,
    "weighted_trend_score": 0.91,
    "competitor_freshness_days": 1,
    "demand_score": 0.95,
    "high_demand": true,
    "performance_level": "low",
    "editorial_quadrant": "opportunity",
    "what_happened": "Pertamina menaikkan harga BBM non-subsidi Pertamax, Dexlite, dan Pertamina Dex mulai 1 Mei 2025, dipicu pelemahan rupiah dan lonjakan harga minyak dunia ke level $94/barel.",
    "parties_involved": ["Pertamina", "DPR RI Komisi VII", "Asosiasi Pengusaha Logistik", "LPEM UI"],
    "editorial_angle": "Investigasi: apakah Pertamina melakukan kajian dampak inflasi sebelum menaikkan harga? Minta dokumen RKAP 2025 dan bandingkan proyeksi dampak inflasi BI vs kenaikan aktual.",
    "bullet_insights": ["8 kompetitor sudah menulis, Tempo belum hadir", "3 keyword trend aktif minggu ini", "Topik konsumsi publik luas — potensi trafik tinggi"],
    "insight_calculated_at": "2026-05-09T06:05:00Z",
    "is_stale": false,
    "sub_clusters": null,
    "parent_cluster": null,
    "sibling_clusters": null,
    "members": [
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000001",
        "title": "Pertamina Naikkan Harga BBM Non-Subsidi per 1 Mei 2025",
        "url": "https://www.kompas.com/ekonomi/pertamina-bbm-naik",
        "first_paragraph": "PT Pertamina (Persero) resmi menaikkan harga BBM non-subsidi jenis Pertamax, Dexlite, dan Pertamina Dex mulai 1 Mei 2025. Kenaikan ini dipicu oleh melemahnya nilai tukar rupiah dan kenaikan harga minyak mentah dunia.",
        "published_at": "2025-04-30T06:30:00Z",
        "source_name": "Kompas",
        "relevance_score": 0.97
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000002",
        "title": "Harga Pertamax Tembus Rp 14.500, Masyarakat Keluhkan Beban",
        "url": "https://www.cnnindonesia.com/ekonomi/pertamax-14500",
        "first_paragraph": "Harga Pertamax di SPBU Pertamina kini mencapai Rp 14.500 per liter, naik dari sebelumnya Rp 13.700. Kenaikan ini disambut keluhan dari masyarakat kelas menengah yang bergantung pada BBM non-subsidi.",
        "published_at": "2025-04-30T08:15:00Z",
        "source_name": "CNN Indonesia",
        "relevance_score": 0.92
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000003",
        "title": "DPR Minta Pemerintah Jelaskan Alasan Kenaikan BBM",
        "url": "https://www.detik.com/finance/berita/dpr-bbm-naik",
        "first_paragraph": "Komisi VII DPR RI meminta pemerintah segera menjelaskan alasan di balik keputusan menaikkan harga BBM non-subsidi. Sejumlah anggota dewan khawatir kenaikan ini akan memicu inflasi yang membebani masyarakat.",
        "published_at": "2025-04-30T09:45:00Z",
        "source_name": "Detik Finance",
        "relevance_score": 0.88
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000004",
        "title": "Pengusaha Logistik Keberatan Harga BBM Naik, Ancam Naikkan Tarif",
        "url": "https://www.bisnis.com/ekonomi/logistik-bbm",
        "first_paragraph": "Asosiasi Pengusaha Truk dan Logistik Indonesia menyatakan keberatan atas kenaikan harga BBM dan mengancam akan menaikkan tarif pengiriman barang hingga 15 persen, yang berpotensi mendorong harga barang konsumsi.",
        "published_at": "2025-04-30T11:00:00Z",
        "source_name": "Bisnis Indonesia",
        "relevance_score": 0.84
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000005",
        "title": "Ekonom: Kenaikan BBM Bisa Picu Inflasi 0,4 Persen",
        "url": "https://www.tempo.co/ekonomi/inflasi-bbm",
        "first_paragraph": "Ekonom dari LPEM UI memperkirakan kenaikan harga BBM non-subsidi akan mendorong inflasi sebesar 0,4 persen pada Mei 2025, terutama melalui transmisi ke harga transportasi dan distribusi barang.",
        "published_at": "2025-04-30T13:20:00Z",
        "source_name": "Tempo",
        "relevance_score": 0.81
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000006",
        "title": "SPBU Swasta Ikut Naikkan Harga BBM Setelah Pertamina",
        "url": "https://www.republika.co.id/ekonomi/spbu-swasta-bbm",
        "first_paragraph": "Menyusul kenaikan Pertamina, SPBU swasta seperti Shell, BP-AKR, dan Vivo juga menaikkan harga. Shell V-Power kini dibanderol Rp 16.100 per liter, naik Rp 400 dari sebelumnya.",
        "published_at": "2025-04-30T14:50:00Z",
        "source_name": "Republika",
        "relevance_score": 0.76
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000007",
        "title": "Pertamina: Kenaikan Harga BBM Sudah Melalui Kajian Mendalam",
        "url": "https://www.antara.co.id/berita/pertamina-bbm-kajian",
        "first_paragraph": "SVP Corporate Communication Pertamina menyatakan kenaikan harga BBM non-subsidi telah melalui kajian mendalam terhadap kondisi pasar global dan nilai tukar rupiah, serta disetujui oleh pemegang saham.",
        "published_at": "2025-04-30T16:10:00Z",
        "source_name": "Antara",
        "relevance_score": 0.72
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000008",
        "title": "Analisis: Tiga Faktor Pendorong Kenaikan BBM Pertamina",
        "url": "https://www.cnbcindonesia.com/market/analisis-bbm-pertamina",
        "first_paragraph": "Tiga faktor utama mendorong Pertamina menaikkan harga BBM: dolar AS menguat ke Rp 16.200, harga minyak Brent naik 12% dalam sebulan, dan subsidi pemerintah yang tidak mencakup produk non-subsidi.",
        "published_at": "2025-05-01T07:30:00Z",
        "source_name": "CNBC Indonesia",
        "relevance_score": 0.69
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000009",
        "title": "Sopir Ojol Keluhkan Kenaikan BBM: Tarif Tidak Ikut Naik",
        "url": "https://www.detik.com/finance/ojol-bbm-naik",
        "first_paragraph": "Pengemudi ojek online yang mayoritas menggunakan Pertamax mengeluh kenaikan BBM membebani operasional, sementara tarif platform tidak ikut disesuaikan. Beberapa driver mengancam mogok.",
        "published_at": "2025-05-01T09:00:00Z",
        "source_name": "Detik Finance",
        "relevance_score": 0.65
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000010",
        "title": "BI: Dampak Kenaikan BBM ke Inflasi Masih Terkendali",
        "url": "https://www.bisnis.com/ekonomi/bi-inflasi-bbm",
        "first_paragraph": "Bank Indonesia menyatakan dampak kenaikan harga BBM non-subsidi terhadap inflasi masih terkendali dalam target 2,5±1 persen, dengan catatan tidak ada guncangan eksternal lebih lanjut.",
        "published_at": "2025-05-01T11:15:00Z",
        "source_name": "Bisnis Indonesia",
        "relevance_score": 0.61
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000011",
        "title": "Kemenkeu Pastikan Subsidi Pertalite dan Solar Tidak Berubah",
        "url": "https://www.kompas.com/ekonomi/kemenkeu-subsidi-bbm",
        "first_paragraph": "Kementerian Keuangan memastikan subsidi untuk Pertalite dan Solar tidak berubah meski Pertamax naik. Anggaran subsidi BBM 2025 tetap Rp 189 triliun sesuai APBN.",
        "published_at": "2025-05-01T13:45:00Z",
        "source_name": "Kompas",
        "relevance_score": 0.57
      },
      {
        "id": "b1c2d3e4-0001-4000-8000-000000000012",
        "title": "Pakar Energi: Indonesia Harus Percepat Transisi ke Kendaraan Listrik",
        "url": "https://www.republika.co.id/ekonomi/transisi-ev-bbm",
        "first_paragraph": "Kenaikan BBM Pertamina dinilai pakar energi sebagai momen yang tepat untuk mempercepat transisi ke kendaraan listrik. Pemerintah didorong memperluas subsidi untuk motor dan mobil listrik kalangan menengah.",
        "published_at": "2025-05-01T15:00:00Z",
        "source_name": "Republika",
        "relevance_score": 0.52
      }
    ]
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/packages/api/tests/mocks/fixtures/cluster-detail.json
  git commit -m "feat(demo): enrich cluster-detail.json with full insight fields and 12 members"
  ```

---

## Task 5: Create cluster-details-map.json (clusters 2–5)

**Files:**
- Create: `frontend/packages/api/tests/mocks/fixtures/cluster-details-map.json`

Rich detail for Sidang MK, Korupsi Dana Desa, PPRT, and Prabowo-Xi.

- [ ] **Step 1: Create cluster-details-map.json**

  ```json
  {
    "a1b2c3d4-0001-4000-8000-000000000002": {
      "id": "a1b2c3d4-0001-4000-8000-000000000002",
      "label": "Sidang MK Sengketa Pilkada Kaltim",
      "member_count": 18,
      "is_current": true,
      "created_at": "2026-05-09T06:00:00Z",
      "trend_velocity": 0.712,
      "competitor_count": 6,
      "trend_match_count": 2,
      "tempo_covered": false,
      "last_internal_days_ago": null,
      "underperformed": false,
      "parent_cluster_id": null,
      "weighted_trend_score": 0.78,
      "competitor_freshness_days": 2,
      "demand_score": 0.82,
      "high_demand": true,
      "performance_level": "low",
      "editorial_quadrant": "opportunity",
      "what_happened": "MK menyidangkan sengketa hasil Pilkada Kaltim 2024 yang diajukan pasangan calon kalah, dengan potensi putusan dalam dua minggu ke depan.",
      "parties_involved": ["Mahkamah Konstitusi", "Pasangan Calon Kaltim", "KPU Kaltim", "Bawaslu"],
      "editorial_angle": "Liputan langsung sidang MK: fokus pada kualitas bukti yang diajukan dan kemungkinan preseden putusan untuk sengketa pilkada serupa di daerah lain.",
      "bullet_insights": ["6 kompetitor aktif meliput, Tempo belum", "Deadline putusan menciptakan urgensi editorial", "2 keyword trend terkait aktif"],
      "insight_calculated_at": "2026-05-09T06:05:00Z",
      "is_stale": false,
      "sub_clusters": null,
      "parent_cluster": null,
      "sibling_clusters": null,
      "members": [
        {
          "id": "c2d3e4f5-0001-4000-8000-000000000001",
          "title": "MK Gelar Sidang Sengketa Pilkada Kaltim, KPU Siapkan Bukti",
          "url": "https://www.kompas.com/nasional/mk-sidang-pilkada-kaltim",
          "first_paragraph": "Mahkamah Konstitusi menggelar sidang perdana sengketa hasil Pilkada Kaltim 2024. KPU Kaltim hadir dengan 200 halaman bukti perolehan suara, sementara pemohon mengklaim ada penggelembungan di 3 kabupaten.",
          "published_at": "2025-04-28T09:00:00Z",
          "source_name": "Kompas",
          "relevance_score": 0.96
        },
        {
          "id": "c2d3e4f5-0002-4000-8000-000000000001",
          "title": "Pasangan Calon Kaltim Ajukan 12 Poin Keberatan ke MK",
          "url": "https://www.detik.com/news/mk-pilkada-kaltim-gugatan",
          "first_paragraph": "Kuasa hukum pasangan calon Kaltim yang kalah mengajukan 12 poin keberatan dalam gugatan ke MK, termasuk dugaan money politics di empat kecamatan dan manipulasi data di sistem KPU.",
          "published_at": "2025-04-27T14:30:00Z",
          "source_name": "Detik",
          "relevance_score": 0.91
        },
        {
          "id": "c2d3e4f5-0003-4000-8000-000000000001",
          "title": "Kuasa Hukum: Ada Penggelembungan Suara di 3 Kabupaten Kaltim",
          "url": "https://www.cnnindonesia.com/nasional/kaltim-mk-sengketa",
          "first_paragraph": "Tim kuasa hukum pemohon membeberkan dugaan penggelembungan suara di Kutai Kartanegara, Berau, dan Paser. Mereka mengklaim ada selisih 18.000 suara yang tidak bisa dijelaskan oleh KPU setempat.",
          "published_at": "2025-04-28T16:00:00Z",
          "source_name": "CNN Indonesia",
          "relevance_score": 0.85
        },
        {
          "id": "c2d3e4f5-0004-4000-8000-000000000001",
          "title": "KPU Kaltim Percaya Diri Hadapi Sengketa di MK",
          "url": "https://www.antara.co.id/nasional/kpu-kaltim-mk",
          "first_paragraph": "Ketua KPU Kaltim menyatakan pihaknya percaya diri menghadapi sengketa di MK karena seluruh tahapan pilkada sudah sesuai prosedur dan rekapitulasi berjenjang telah diverifikasi Bawaslu.",
          "published_at": "2025-04-29T10:15:00Z",
          "source_name": "Antara",
          "relevance_score": 0.79
        },
        {
          "id": "c2d3e4f5-0005-4000-8000-000000000001",
          "title": "Pengamat: Putusan MK Pilkada Kaltim Bisa Jadi Preseden Penting",
          "url": "https://www.bisnis.com/nasional/mk-pilkada-preseden",
          "first_paragraph": "Pakar hukum tata negara menilai sengketa Pilkada Kaltim memiliki potensi menjadi preseden bagi sengketa pilkada daerah lain yang menghadapi masalah sistem rekapitulasi digital KPU.",
          "published_at": "2025-04-29T13:00:00Z",
          "source_name": "Bisnis Indonesia",
          "relevance_score": 0.72
        }
      ]
    },
    "a1b2c3d4-0001-4000-8000-000000000003": {
      "id": "a1b2c3d4-0001-4000-8000-000000000003",
      "label": "Korupsi Dana Desa Jawa Tengah",
      "member_count": 31,
      "is_current": true,
      "created_at": "2026-05-09T06:00:00Z",
      "trend_velocity": 0.68,
      "competitor_count": 5,
      "trend_match_count": 2,
      "tempo_covered": true,
      "last_internal_days_ago": 3,
      "underperformed": false,
      "parent_cluster_id": null,
      "weighted_trend_score": 0.71,
      "competitor_freshness_days": 2,
      "demand_score": 0.75,
      "high_demand": true,
      "performance_level": "high",
      "editorial_quadrant": "winning",
      "what_happened": "Kejaksaan Tinggi Jawa Tengah menetapkan 12 kepala desa sebagai tersangka korupsi dana desa senilai Rp 4,8 miliar di 3 kabupaten melalui proyek fiktif dan markup material bangunan.",
      "parties_involved": ["Kejati Jawa Tengah", "12 Kepala Desa", "Kemendesa", "BPK"],
      "editorial_angle": "Analisis pola: apakah ada distributor rekanan yang sama di ketiga kabupaten? Bandingkan modus dengan kasus korupsi dana desa di Jatim dan NTB — cari pola sistemik yang menjangkau banyak daerah.",
      "bullet_insights": ["Tempo sudah meliput 3 hari lalu dengan trafik bagus", "5 kompetitor aktif — butuh angle investigatif untuk membedakan", "BPK temukan pola serupa di 5 provinsi lain"],
      "insight_calculated_at": "2026-05-09T06:05:00Z",
      "is_stale": false,
      "sub_clusters": null,
      "parent_cluster": null,
      "sibling_clusters": null,
      "members": [
        {
          "id": "c3d4e5f6-0001-4000-8000-000000000001",
          "title": "Kejati Jateng Tetapkan 12 Kades Tersangka Korupsi Dana Desa Rp 4,8 M",
          "url": "https://www.kompas.com/nasional/kejati-jateng-kades-korupsi",
          "first_paragraph": "Kejaksaan Tinggi Jawa Tengah menetapkan 12 kepala desa di Kabupaten Klaten, Boyolali, dan Sragen sebagai tersangka korupsi dana desa total Rp 4,8 miliar. Modus: proyek fiktif pembangunan jalan desa dan pengadaan material fiktif.",
          "published_at": "2025-04-25T09:30:00Z",
          "source_name": "Kompas",
          "relevance_score": 0.97
        },
        {
          "id": "c3d4e5f6-0002-4000-8000-000000000001",
          "title": "Modus Korupsi Dana Desa Jateng: Proyek Fiktif dan Rekanan Satu Orang",
          "url": "https://www.detik.com/news/modus-korupsi-dana-desa-jateng",
          "first_paragraph": "Penyelidikan Kejati Jateng mengungkap modus serupa di ketiga kabupaten: dana desa digunakan untuk proyek pembangunan infrastruktur yang tidak ada fisiknya, dengan dokumen pengadaan dari rekanan yang sama.",
          "published_at": "2025-04-25T14:00:00Z",
          "source_name": "Detik",
          "relevance_score": 0.90
        },
        {
          "id": "c3d4e5f6-0003-4000-8000-000000000001",
          "title": "BPK Temukan Pola Korupsi Dana Desa Serupa di 5 Provinsi",
          "url": "https://www.tempo.co/nasional/bpk-korupsi-dana-desa-5-provinsi",
          "first_paragraph": "Badan Pemeriksa Keuangan mengungkapkan temuan audit: pola korupsi dana desa melalui proyek fiktif dan rekanan fiktif teridentifikasi di Jawa Tengah, Jawa Timur, NTB, Sulawesi Selatan, dan Sumatera Utara.",
          "published_at": "2025-04-26T11:00:00Z",
          "source_name": "Tempo",
          "relevance_score": 0.86
        },
        {
          "id": "c3d4e5f6-0004-4000-8000-000000000001",
          "title": "Kemendesa Siapkan Sistem Audit Digital Dana Desa Pascakasus Jateng",
          "url": "https://www.antara.co.id/nasional/kemendesa-audit-digital-dana-desa",
          "first_paragraph": "Kementerian Desa PDTT mengumumkan akan menerapkan sistem audit digital berbasis blockchain untuk dana desa mulai 2026 sebagai respons atas maraknya kasus korupsi, termasuk di Jawa Tengah.",
          "published_at": "2025-04-27T08:45:00Z",
          "source_name": "Antara",
          "relevance_score": 0.79
        },
        {
          "id": "c3d4e5f6-0005-4000-8000-000000000001",
          "title": "ICW: Korupsi Dana Desa Meningkat 3x Lipat dalam 5 Tahun",
          "url": "https://www.cnnindonesia.com/nasional/icw-korupsi-dana-desa-meningkat",
          "first_paragraph": "Indonesia Corruption Watch mencatat kasus korupsi dana desa meningkat tiga kali lipat dari 17 kasus pada 2019 menjadi 51 kasus pada 2024, dengan total kerugian negara mencapai Rp 82 miliar.",
          "published_at": "2025-04-27T16:30:00Z",
          "source_name": "CNN Indonesia",
          "relevance_score": 0.73
        },
        {
          "id": "c3d4e5f6-0006-4000-8000-000000000001",
          "title": "Pakar: Pengawasan Dana Desa Perlu Melibatkan Warga Secara Aktif",
          "url": "https://www.bisnis.com/nasional/pengawasan-dana-desa-warga",
          "first_paragraph": "Pakar kebijakan publik Universitas Indonesia menyarankan model pengawasan dana desa yang melibatkan forum warga sebagai lapis pertama deteksi penyimpangan, sebelum sampai ke inspektorat daerah.",
          "published_at": "2025-04-28T10:00:00Z",
          "source_name": "Bisnis Indonesia",
          "relevance_score": 0.65
        }
      ]
    },
    "a1b2c3d4-0001-4000-8000-000000000004": {
      "id": "a1b2c3d4-0001-4000-8000-000000000004",
      "label": "Pengesahan RUU PPRT DPR",
      "member_count": 12,
      "is_current": true,
      "created_at": "2026-05-09T06:00:00Z",
      "trend_velocity": 0.615,
      "competitor_count": 4,
      "trend_match_count": 1,
      "tempo_covered": true,
      "last_internal_days_ago": null,
      "underperformed": false,
      "parent_cluster_id": null,
      "weighted_trend_score": 0.63,
      "competitor_freshness_days": 1,
      "demand_score": 0.68,
      "high_demand": true,
      "performance_level": null,
      "editorial_quadrant": "too_early",
      "what_happened": "DPR memasukkan RUU Perlindungan Pekerja Rumah Tangga ke Prolegnas 2025, dua belas tahun setelah pertama kali diajukan pada 2012.",
      "parties_involved": ["DPR RI Baleg", "Jaringan Nasional Advokasi PRT", "ILO", "Komnas HAM"],
      "editorial_angle": "Follow-up langsung ke Baleg DPR: siapa fraksi yang masih menghambat, dan perubahan apa dari draf 2012 yang membuat RUU ini berbeda kali ini?",
      "bullet_insights": ["Artikel Tempo terlalu baru — GSC butuh 1–3 hari", "Pantau besok untuk melihat trafik awal", "4 kompetitor sudah menulis angle serupa"],
      "insight_calculated_at": "2026-05-09T06:05:00Z",
      "is_stale": false,
      "sub_clusters": null,
      "parent_cluster": null,
      "sibling_clusters": null,
      "members": [
        {
          "id": "c4d5e6f7-0001-4000-8000-000000000001",
          "title": "DPR Masukkan RUU PPRT ke Prolegnas 2025, Aktivis Sambut Positif",
          "url": "https://www.kompas.com/nasional/ruu-pprt-prolegnas-2025",
          "first_paragraph": "Badan Legislasi DPR RI resmi memasukkan RUU Perlindungan Pekerja Rumah Tangga ke Program Legislasi Nasional 2025. Ini adalah pertama kalinya RUU yang sudah ada sejak 2012 ini masuk Prolegnas prioritas.",
          "published_at": "2025-05-08T10:00:00Z",
          "source_name": "Kompas",
          "relevance_score": 0.95
        },
        {
          "id": "c4d5e6f7-0002-4000-8000-000000000001",
          "title": "12 Tahun Mangkrak, RUU PPRT Akhirnya Masuk Prolegnas Prioritas",
          "url": "https://www.tempo.co/nasional/ruu-pprt-prolegnas-12-tahun",
          "first_paragraph": "Setelah 12 tahun terkatung-katung di DPR, RUU Perlindungan Pekerja Rumah Tangga akhirnya masuk Prolegnas Prioritas 2025. Jaringan Advokasi PRT menyambut positif namun mengingatkan perlunya pengawalan ketat.",
          "published_at": "2025-05-08T11:30:00Z",
          "source_name": "Tempo",
          "relevance_score": 0.89
        },
        {
          "id": "c4d5e6f7-0003-4000-8000-000000000001",
          "title": "ILO Desak Indonesia Segera Sahkan Perlindungan Pekerja Rumah Tangga",
          "url": "https://www.antara.co.id/nasional/ilo-pprt-indonesia",
          "first_paragraph": "Organisasi Buruh Internasional (ILO) mendesak Indonesia segera mengesahkan UU Perlindungan Pekerja Rumah Tangga. Indonesia adalah satu dari sedikit negara pengirim TKI yang belum memiliki regulasi khusus PRT.",
          "published_at": "2025-05-07T14:00:00Z",
          "source_name": "Antara",
          "relevance_score": 0.82
        },
        {
          "id": "c4d5e6f7-0004-4000-8000-000000000001",
          "title": "Koalisi PRT: Draf Terbaru RUU PPRT Lebih Baik dari Versi 2012",
          "url": "https://www.cnnindonesia.com/nasional/draf-ruu-pprt-2025",
          "first_paragraph": "Koalisi organisasi advokasi PRT menyatakan draf terbaru RUU PPRT 2025 memuat klausul perlindungan yang lebih kuat dibanding versi 2012, termasuk upah minimum, jam kerja maksimum, dan hak cuti.",
          "published_at": "2025-05-08T15:45:00Z",
          "source_name": "CNN Indonesia",
          "relevance_score": 0.74
        }
      ]
    },
    "a1b2c3d4-0001-4000-8000-000000000005": {
      "id": "a1b2c3d4-0001-4000-8000-000000000005",
      "label": "Prabowo-Xi Jinping Bilateral Bali",
      "member_count": 9,
      "is_current": true,
      "created_at": "2026-05-09T06:00:00Z",
      "trend_velocity": 0.548,
      "competitor_count": 7,
      "trend_match_count": 2,
      "tempo_covered": false,
      "last_internal_days_ago": null,
      "underperformed": false,
      "parent_cluster_id": null,
      "weighted_trend_score": 0.59,
      "competitor_freshness_days": 1,
      "demand_score": 0.61,
      "high_demand": true,
      "performance_level": "low",
      "editorial_quadrant": "opportunity",
      "what_happened": "Presiden Prabowo bertemu Xi Jinping di sela G20 Bali, menghasilkan komitmen investasi senilai $8,5 miliar di sektor infrastruktur dan transisi energi.",
      "parties_involved": ["Prabowo Subianto", "Xi Jinping", "Kementerian Investasi", "BKPM"],
      "editorial_angle": "Analisis konkret: bandingkan $8,5 miliar dengan realisasi janji investasi China era Jokowi — berapa yang benar-benar masuk vs tertahan sebagai komitmen di atas kertas.",
      "bullet_insights": ["7 kompetitor menulis, Tempo belum hadir", "Angle komparatif era Jokowi vs Prabowo belum disentuh kompetitor", "2 keyword trend aktif terkait G20 Bali"],
      "insight_calculated_at": "2026-05-09T06:05:00Z",
      "is_stale": false,
      "sub_clusters": null,
      "parent_cluster": null,
      "sibling_clusters": null,
      "members": [
        {
          "id": "c5d6e7f8-0001-4000-8000-000000000001",
          "title": "Prabowo dan Xi Jinping Bilateral di Bali, Sepakati Investasi $8,5 Miliar",
          "url": "https://www.kompas.com/nasional/prabowo-xi-jinping-bali-investasi",
          "first_paragraph": "Presiden Prabowo Subianto dan Presiden China Xi Jinping menggelar pertemuan bilateral di sela G20 Bali. Hasilnya: nota kesepahaman investasi senilai $8,5 miliar mencakup proyek rel kereta Kalimantan dan PLTS di NTT.",
          "published_at": "2025-05-05T18:00:00Z",
          "source_name": "Kompas",
          "relevance_score": 0.96
        },
        {
          "id": "c5d6e7f8-0002-4000-8000-000000000001",
          "title": "Rincian Investasi China: Infrastruktur Kalimantan dan Energi Surya NTT",
          "url": "https://www.bisnis.com/ekonomi/investasi-china-indonesia-rincian",
          "first_paragraph": "Dari total $8,5 miliar komitmen investasi China, $4,2 miliar dialokasikan untuk proyek rel kereta Kalimantan Tengah-Selatan, $2,8 miliar untuk PLTS skala besar di NTT, dan sisanya untuk infrastruktur pelabuhan.",
          "published_at": "2025-05-06T09:00:00Z",
          "source_name": "Bisnis Indonesia",
          "relevance_score": 0.90
        },
        {
          "id": "c5d6e7f8-0003-4000-8000-000000000001",
          "title": "Analis: Komitmen Investasi China Perlu Dikawal Realisasinya",
          "url": "https://www.cnbcindonesia.com/market/komitmen-investasi-china-realisasi",
          "first_paragraph": "Ekonom CSIS mengingatkan bahwa dari $23 miliar komitmen investasi China era Jokowi 2019–2023, hanya 34% yang terealisasi. Ia mendorong pemerintah Prabowo membuat mekanisme monitoring yang lebih ketat.",
          "published_at": "2025-05-06T14:30:00Z",
          "source_name": "CNBC Indonesia",
          "relevance_score": 0.83
        },
        {
          "id": "c5d6e7f8-0004-4000-8000-000000000001",
          "title": "Kementerian Investasi Siapkan Roadmap Penerimaan Investasi China 2025",
          "url": "https://www.antara.co.id/ekonomi/kementerianinvestasi-roadmap-china",
          "first_paragraph": "BKPM menyiapkan roadmap penerimaan dan monitoring investasi China pasca-bilateral Bali, dengan target 60% komitmen terealisasi dalam 3 tahun, lebih tinggi dari rata-rata realisasi era sebelumnya.",
          "published_at": "2025-05-07T10:00:00Z",
          "source_name": "Antara",
          "relevance_score": 0.76
        },
        {
          "id": "c5d6e7f8-0005-4000-8000-000000000001",
          "title": "Aktivis: Investasi China Harus Prioritaskan Tenaga Kerja Lokal",
          "url": "https://www.cnnindonesia.com/nasional/aktivis-investasi-china-tenaga-lokal",
          "first_paragraph": "Koalisi buruh dan LSM lingkungan mendesak pemerintah memastikan proyek investasi China era Prabowo memprioritaskan pekerja lokal dan memenuhi standar lingkungan AMDAL, belajar dari masalah era sebelumnya.",
          "published_at": "2025-05-07T16:15:00Z",
          "source_name": "CNN Indonesia",
          "relevance_score": 0.68
        }
      ]
    }
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/packages/api/tests/mocks/fixtures/cluster-details-map.json
  git commit -m "feat(demo): add cluster-details-map.json with rich insight for clusters 2-5"
  ```

---

## Task 6: Update cluster/:id handler to use details map

**Files:**
- Modify: `frontend/packages/app/src/mocks/handlers.ts`

Add import for `cluster-details-map.json` and update the `/clusters/:id` handler to check the map first.

- [ ] **Step 1: Add import for details map**

  At the top of `handlers.ts`, add this import after the existing imports:
  ```ts
  import clusterDetailsMap from "../../../api/tests/mocks/fixtures/cluster-details-map.json"
  ```

- [ ] **Step 2: Replace the existing clusters/:id handler**

  Find the existing handler (around line 154):
  ```ts
  http.get(`${BASE}/clusters/:id`, ({ params }) => {
  ```

  Replace the entire handler with:
  ```ts
  http.get(`${BASE}/clusters/:id`, ({ params }) => {
    const { id } = params as { id: string }
    if (id in clusterDetailsMap) {
      return HttpResponse.json(clusterDetailsMap[id as keyof typeof clusterDetailsMap])
    }
    if (id === clusterDetail.id) return HttpResponse.json(clusterDetail)
    const cluster = morningClusters.clusters.find((c) => c.id === id)
    if (!cluster) return HttpResponse.json({ detail: "Not found" }, { status: 404 })
    const count = Math.min(cluster.member_count ?? 5, 8)
    return HttpResponse.json({
      ...cluster,
      members: generateMembers(cluster, count),
      sub_clusters: null,
      parent_cluster: null,
      sibling_clusters: null,
      is_stale: morningClusters.is_stale,
    })
  }),
  ```

- [ ] **Step 3: Verify cluster detail navigation works in dev**

  With dev server running, navigate to Morning view → click any of the top 5 clusters (BBM, Sidang MK, Korupsi, PPRT, Prabowo). Each should show filled `what_happened`, `parties_involved`, and `editorial_angle` in the detail view. Clusters 6–10 should show synthetic data via fallback.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/packages/app/src/mocks/handlers.ts
  git commit -m "feat(demo): update cluster/:id handler to serve rich details map"
  ```

---

## Task 7: Add schema fixture validation tests

**Files:**
- Modify: `frontend/packages/api/tests/schemas.test.ts`

Validate that the enriched fixtures parse correctly against their schemas. These catch fixture shape errors before the app ever runs.

- [ ] **Step 1: Add fixture validation tests**

  At the top of `schemas.test.ts` (located at `frontend/packages/api/tests/schemas.test.ts`), add these imports after the existing imports:
  ```ts
  import morningClusters from "./mocks/fixtures/morning-clusters.json"
  import clusterDetail from "./mocks/fixtures/cluster-detail.json"
  import clusterDetailsMap from "./mocks/fixtures/cluster-details-map.json"
  import { ClusterListResponseSchema, ClusterDetailSchema } from "../src/schemas.js"
  ```

  Add these test blocks at the end of `schemas.test.ts`:
  ```ts
  describe("ClusterListResponseSchema — morning-clusters fixture", () => {
    test("validates enriched morning-clusters.json", () => {
      const result = ClusterListResponseSchema.safeParse(morningClusters)
      expect(result.success).toBe(true)
    })

    test("all 10 clusters have editorial_quadrant set", () => {
      const result = ClusterListResponseSchema.safeParse(morningClusters)
      expect(result.success).toBe(true)
      if (!result.success) return
      for (const c of result.data.clusters) {
        expect(c.editorial_quadrant).not.toBeNull()
      }
    })

    test("quadrant distribution matches expected demo counts", () => {
      const result = ClusterListResponseSchema.safeParse(morningClusters)
      expect(result.success).toBe(true)
      if (!result.success) return
      const counts = { opportunity: 0, winning: 0, evergreen: 0, ignore: 0, too_early: 0 }
      for (const c of result.data.clusters) {
        const q = c.editorial_quadrant as keyof typeof counts | null
        if (q && q in counts) counts[q]++
      }
      expect(counts.opportunity).toBe(3)
      expect(counts.winning).toBe(2)
      expect(counts.too_early).toBe(1)
      expect(counts.evergreen).toBe(1)
      expect(counts.ignore).toBe(3)
    })
  })

  describe("ClusterDetailSchema — fixture validation", () => {
    test("cluster-detail.json (BBM) validates", () => {
      expect(ClusterDetailSchema.safeParse(clusterDetail).success).toBe(true)
    })

    test("all entries in cluster-details-map.json validate", () => {
      for (const detail of Object.values(clusterDetailsMap)) {
        const result = ClusterDetailSchema.safeParse(detail)
        expect(result.success).toBe(true)
      }
    })

    test("BBM cluster has non-null insight fields", () => {
      const result = ClusterDetailSchema.safeParse(clusterDetail)
      expect(result.success).toBe(true)
      if (!result.success) return
      expect(result.data.what_happened).not.toBeNull()
      expect(result.data.editorial_angle).not.toBeNull()
      expect(result.data.parties_involved).not.toBeNull()
    })

    test("map entries each have at least 4 members", () => {
      for (const detail of Object.values(clusterDetailsMap)) {
        const result = ClusterDetailSchema.safeParse(detail)
        expect(result.success).toBe(true)
        if (!result.success) continue
        expect(result.data.members.length).toBeGreaterThanOrEqual(4)
      }
    })
  })
  ```

- [ ] **Step 2: Run the tests**

  From `frontend/`:
  ```bash
  bun test packages/api/tests/schemas.test.ts
  ```

  Expected output: all tests pass, including the new fixture validation blocks.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/packages/api/tests/schemas.test.ts
  git commit -m "test(demo): add schema fixture validation for morning-clusters and cluster-details-map"
  ```

---

## Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/demo.yml`

Builds the app with mock mode and deploys to `gh-pages` branch on every push to `master`.

- [ ] **Step 1: Ensure the `gh-pages` branch exists (one-time setup)**

  GitHub Pages must be enabled in the repo settings. Go to **Settings → Pages → Source** and set it to `gh-pages` branch. This only needs to be done once.

- [ ] **Step 2: Create .github/workflows/demo.yml**

  Create the file at `.github/workflows/demo.yml`:
  ```yaml
  name: Deploy Demo to GitHub Pages

  on:
    push:
      branches: [master]
    workflow_dispatch:

  permissions:
    contents: write

  jobs:
    deploy:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - uses: oven-sh/setup-bun@v2
          with:
            bun-version: latest

        - name: Install dependencies
          run: cd frontend && bun install --frozen-lockfile

        - name: Build with mock mode
          run: cd frontend/packages/app && bun run build
          env:
            VITE_MOCK: "true"
            VITE_BASE: "/content-intelligence/"

        - name: Copy index.html as 404.html (React Router fix)
          run: cp frontend/packages/app/dist/index.html frontend/packages/app/dist/404.html

        - name: Deploy to GitHub Pages
          uses: peaceiris/actions-gh-pages@v4
          with:
            github_token: ${{ secrets.GITHUB_TOKEN }}
            publish_dir: ./frontend/packages/app/dist
            force_orphan: true
  ```

- [ ] **Step 3: Commit and push**

  ```bash
  git add .github/workflows/demo.yml
  git commit -m "ci: add GitHub Pages demo deployment workflow"
  git push origin master
  ```

- [ ] **Step 4: Verify workflow runs**

  Go to the repo on GitHub → **Actions** tab. The "Deploy Demo to GitHub Pages" workflow should appear and run. Wait for it to complete (green checkmark). Then visit `https://<org>.github.io/content-intelligence/` to confirm the demo loads.

  If the workflow fails on the `bun install` step with a lockfile error, try removing `--frozen-lockfile` from the install command.

---

## Self-Review Checklist

Spec section → task coverage:

| Spec requirement | Task |
|-----------------|------|
| `VITE_MOCK=true` activates MSW in prod build | Task 1 |
| `base` URL for GitHub Pages subpath | Task 1 |
| `GET /clusters/quadrant-summary` mock | Task 2 |
| `GET /clusters/quadrant/:quadrant` mock | Task 2 |
| `stages` field in cluster run response | Task 2 |
| morning-clusters enriched with quadrant data | Task 3 |
| cluster-detail.json insight fields + 12 members | Task 4 |
| cluster-details-map.json for clusters 2–5 | Task 5 |
| handler checks map before synthetic fallback | Task 6 |
| Schema validation tests for new fixtures | Task 7 |
| GitHub Actions workflow | Task 8 |
| `404.html` copy for React Router deep links | Task 8 |
