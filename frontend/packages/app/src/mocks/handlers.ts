import { http, HttpResponse } from "msw"
import morningClusters from "../../../api/tests/mocks/fixtures/morning-clusters.json"
import deferredClusters from "../../../api/tests/mocks/fixtures/deferred-clusters.json"
import clusterDetail from "../../../api/tests/mocks/fixtures/cluster-detail.json"
import clusterDetailsMap from "../../../api/tests/mocks/fixtures/cluster-details-map.json"

const BASE = `${(import.meta.env.BASE_URL ?? "/").replace(/\/$/, "")}/api/v1`

type MockSource = {
  id: string; name: string; url: string; source_type: string; is_enabled: boolean
  status: string | null; last_fetched_at: string | null; created_at: string; updated_at: string; article_count_24h: number
}

const mockSources: MockSource[] = [
  {
    id: "a1b2c3d4-0001-4000-8000-000000000001",
    name: "Kompas RSS",
    url: "https://rss.kompas.com/nasional",
    source_type: "rss",
    is_enabled: true,
    status: "active",
    last_fetched_at: new Date(Date.now() - 3_600_000).toISOString(),
    created_at: "2025-11-01T00:00:00Z",
    updated_at: new Date(Date.now() - 3_600_000).toISOString(),
    article_count_24h: 142,
  },
  {
    id: "a1b2c3d4-0002-4000-8000-000000000002",
    name: "Tempo Internal",
    url: "https://www.tempo.co/sitemap.xml",
    source_type: "internal",
    is_enabled: true,
    status: "active",
    last_fetched_at: new Date(Date.now() - 7_200_000).toISOString(),
    created_at: "2025-11-01T00:00:00Z",
    updated_at: new Date(Date.now() - 7_200_000).toISOString(),
    article_count_24h: 210,
  },
  {
    id: "a1b2c3d4-0003-4000-8000-000000000003",
    name: "Republika",
    url: "https://www.republika.co.id/rss",
    source_type: "rss",
    is_enabled: false,
    status: "error",
    last_fetched_at: null,
    created_at: "2025-11-15T00:00:00Z",
    updated_at: "2025-11-15T00:00:00Z",
    article_count_24h: 0,
  },
]

const SOURCES = ["Kompas", "Tempo", "Detik.com", "CNN Indonesia", "Republika", "Bisnis.com", "CNBC Indonesia", "Antara"]
const ANGLES = ["Laporan", "Analisis", "Wawancara", "Investigasi", "Breaking", "Opini", "Data", "Eksklusif"]

function generateMembers(cluster: { id: string; label: string | null; member_count: number | null }, count: number) {
  return Array.from({ length: count }, (_, i) => {
    const source = SOURCES[i % SOURCES.length]!
    const angle = ANGLES[Math.floor(i * 1.618) % ANGLES.length]!
    return {
      id: crypto.randomUUID(),
      title: `[${angle}] ${cluster.label ?? "Kluster"} — ${source}`,
      url: `https://example.com/${cluster.id.slice(-4)}/${i}`,
      first_paragraph: null,
      published_at: new Date(Date.now() - i * 7_200_000).toISOString(),
      source_name: source,
      relevance_score: Math.max(0.45, 0.95 - i * 0.05),
    }
  })
}

function generateArticles(page: number, pageSize: number) {
  const total = 48
  const totalPages = Math.ceil(total / pageSize)
  const offset = (page - 1) * pageSize
  const items = Array.from({ length: Math.min(pageSize, Math.max(0, total - offset)) }, (_, i) => {
    const idx = offset + i
    const source = SOURCES[idx % SOURCES.length]!
    const sourceType = idx % 5 === 0 ? "internal" : "rss"
    return {
      id: `${String(idx).padStart(8, "0")}-0001-4000-8000-${String(idx).padStart(12, "0")}`,
      title: `${ANGLES[idx % ANGLES.length]} — Berita ${idx + 1}`,
      url: `https://example.com/articles/${idx}`,
      first_paragraph: `Paragraf pertama artikel nomor ${idx + 1} dari ${source}.`,
      published_at: new Date(Date.now() - idx * 3_600_000).toISOString(),
      created_at: new Date(Date.now() - idx * 3_600_000 + 60_000).toISOString(),
      source_name: source,
      source_type: sourceType,
    }
  })
  return { items, total, page, page_size: pageSize, total_pages: totalPages }
}

export const handlers = [
  http.get(`${BASE}/sources`, () => HttpResponse.json(mockSources)),
  http.post(`${BASE}/sources`, async ({ request }) => {
    const body = await request.json() as { url: string; name?: string; is_enabled?: boolean }
    if (!body.url || !/^https?:\/\/.+/i.test(body.url)) {
      return HttpResponse.json({ detail: "URL tidak valid." }, { status: 422 })
    }
    if (mockSources.some((s) => s.url === body.url)) {
      return HttpResponse.json({ detail: "URL sudah terdaftar." }, { status: 409 })
    }
    const created = {
      id: crypto.randomUUID(),
      name: body.name ?? "",
      url: body.url,
      source_type: "rss" as const,
      is_enabled: body.is_enabled ?? true,
      status: null,
      last_fetched_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      article_count_24h: 0,
    }
    mockSources.push(created)
    return HttpResponse.json(created, { status: 201 })
  }),
  http.delete(`${BASE}/sources/:id`, ({ params }) => {
    const idx = mockSources.findIndex((s) => s.id === params["id"])
    if (idx === -1) return HttpResponse.json({ detail: "Source tidak ditemukan." }, { status: 404 })
    mockSources.splice(idx, 1)
    return new HttpResponse(null, { status: 204 })
  }),
  http.patch(`${BASE}/sources/:id`, async ({ params, request }) => {
    const source = mockSources.find((s) => s.id === params["id"])
    if (!source) return HttpResponse.json({ detail: "Source tidak ditemukan." }, { status: 404 })
    const body = await request.json() as { is_enabled: boolean }
    source.is_enabled = body.is_enabled
    source.updated_at = new Date().toISOString()
    return HttpResponse.json(source)
  }),
  http.get(`${BASE}/clusters/morning`, () => HttpResponse.json(morningClusters)),
  http.get(`${BASE}/clusters/deferred`, () => HttpResponse.json(deferredClusters)),
  http.get(`${BASE}/clusters/current`, () => HttpResponse.json(morningClusters)),
  http.get(`${BASE}/clusters/runs/latest`, () =>
    HttpResponse.json({
      id: "a1b2c3d4-0099-4000-8000-000000000001",
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
  http.get(`${BASE}/articles`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get("page") ?? "1", 10)
    const pageSize = parseInt(url.searchParams.get("page_size") ?? "20", 10)
    return HttpResponse.json(generateArticles(page, pageSize))
  }),
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
  http.get(`${BASE}/health`, () => HttpResponse.json({ status: "ok", db: true })),
  http.get(`${BASE}/trend-signals/latest`, ({ request }) => {
    const url = new URL(request.url)
    const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "10", 10), 50)
    const now = new Date().toISOString()
    const keywords = [
      "Kenaikan Harga BBM", "Sidang MK Pilkada", "Korupsi Dana Desa",
      "PPRT Pengesahan", "Prabowo Xi Jinping", "BPJS Iuran Baru",
      "Karhutla Kalbar", "Startup PHK", "Rupiah Melemah", "CPNS 2025",
    ]
    const signals = keywords.slice(0, limit).map((keyword, i) => ({
      id: crypto.randomUUID(),
      keyword,
      interest_score: Math.round(94 - i * 6.2),
      captured_at: now,
      article_count: Math.max(5, 25 - i * 2),
    }))
    return HttpResponse.json(signals)
  }),
  http.get(`${BASE}/pipeline/status`, () =>
    HttpResponse.json({ cluster_label_score: null, analysis: null }),
  ),
]
