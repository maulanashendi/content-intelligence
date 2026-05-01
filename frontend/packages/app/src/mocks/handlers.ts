import { http, HttpResponse } from "msw"
import morningClusters from "../../../api/tests/mocks/fixtures/morning-clusters.json"
import clusterDetail from "../../../api/tests/mocks/fixtures/cluster-detail.json"

const BASE = "/api/v1"

const SOURCES = ["Kompas", "Tempo", "Detik.com", "CNN Indonesia", "Republika", "Bisnis.com", "CNBC Indonesia", "Antara"]
const ANGLES = ["Laporan", "Analisis", "Wawancara", "Investigasi", "Breaking", "Opini", "Data", "Eksklusif"]

function generateMembers(cluster: { id: string; label: string | null; member_count: number | null }, count: number) {
  return Array.from({ length: count }, (_, i) => {
    const source = SOURCES[i % SOURCES.length]!
    const angle = ANGLES[Math.floor(i * 1.618) % ANGLES.length]!
    return {
      id: `article-${cluster.id.slice(-8)}-${i}`,
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
      id: `mock-article-${String(idx).padStart(4, "0")}`,
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
  http.get(`${BASE}/clusters/morning`, () => HttpResponse.json(morningClusters)),
  http.get(`${BASE}/articles`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get("page") ?? "1", 10)
    const pageSize = parseInt(url.searchParams.get("page_size") ?? "20", 10)
    return HttpResponse.json(generateArticles(page, pageSize))
  }),
  http.get(`${BASE}/clusters/:id`, ({ params }) => {
    const { id } = params as { id: string }
    if (id === clusterDetail.id) return HttpResponse.json(clusterDetail)
    const cluster = allClusters.find((c) => c.id === id)
    if (!cluster) return HttpResponse.json({ detail: "Not found" }, { status: 404 })
    const count = Math.min(cluster.member_count ?? 5, 8)
    return HttpResponse.json({ ...cluster, members: generateMembers(cluster, count) })
  }),
  http.get(`${BASE}/health`, () => HttpResponse.json({ status: "ok", db: true })),
]
