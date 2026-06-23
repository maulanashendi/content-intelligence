import { describe, test, expect } from "bun:test"
import { ContentSourceSchema, ContentSourceListSchema, ArticleSchema, PaginatedArticlesSchema, ClusterListResponseSchema, ClusterDetailSchema, BentoListResponseSchema, VolumeTrendResponseSchema } from "../src/schemas.js"
import morningClusters from "./mocks/fixtures/morning-clusters.json"
import clusterDetail from "./mocks/fixtures/cluster-detail.json"
import clusterDetailsMap from "./mocks/fixtures/cluster-details-map.json"
import bentoClusters from "./mocks/fixtures/bento-clusters.json"
import clusterVolumeTrend from "./mocks/fixtures/cluster-volume-trend.json"

// Minimal valid payload matching what the backend SourceResponse returns.
const VALID_SOURCE = {
  id: "a1b2c3d4-0001-4000-8000-000000000001",
  name: "Kompas RSS",
  url: "https://rss.kompas.com/nasional",
  source_type: "rss",
  is_enabled: true,
  status: "active",
  last_fetched_at: "2026-04-30T06:12:00",
  created_at: "2025-11-01T00:00:00",
  updated_at: "2026-04-30T06:12:00",
  article_count_24h: 142,
}

describe("ContentSourceSchema", () => {
  test("accepts valid source payload from backend", () => {
    const result = ContentSourceSchema.safeParse(VALID_SOURCE)
    expect(result.success).toBe(true)
  })

  test("rejects mock-style id with non-hex characters (e.g. 'cs000001-...')", () => {
    // 's' is not a hex digit — z.string().uuid() must reject this.
    // This was the root cause of "Respons API tidak sesuai skema."
    const result = ContentSourceSchema.safeParse({
      ...VALID_SOURCE,
      id: "cs000001-0000-4000-8000-000000000001",
    })
    expect(result.success).toBe(false)
  })

  test("accepts null status", () => {
    const result = ContentSourceSchema.safeParse({ ...VALID_SOURCE, status: null })
    expect(result.success).toBe(true)
  })

  test("rejects unknown source_type value", () => {
    const result = ContentSourceSchema.safeParse({ ...VALID_SOURCE, source_type: "api" })
    expect(result.success).toBe(false)
  })

  test("accepts null last_fetched_at", () => {
    const result = ContentSourceSchema.safeParse({ ...VALID_SOURCE, last_fetched_at: null })
    expect(result.success).toBe(true)
  })

  test("rejects missing article_count_24h", () => {
    const { article_count_24h: _omit, ...rest } = VALID_SOURCE
    const result = ContentSourceSchema.safeParse(rest)
    expect(result.success).toBe(false)
  })

  test("rejects non-integer article_count_24h", () => {
    const result = ContentSourceSchema.safeParse({ ...VALID_SOURCE, article_count_24h: 1.5 })
    expect(result.success).toBe(false)
  })
})

describe("ContentSourceListSchema", () => {
  test("accepts empty array", () => {
    expect(ContentSourceListSchema.safeParse([]).success).toBe(true)
  })

  test("accepts array of valid sources", () => {
    const result = ContentSourceListSchema.safeParse([
      VALID_SOURCE,
      { ...VALID_SOURCE, id: "b2c3d4e5-0002-4000-8000-000000000002", name: "Tempo Internal", source_type: "internal", status: null },
    ])
    expect(result.success).toBe(true)
  })

  test("rejects array containing a source with invalid id", () => {
    const result = ContentSourceListSchema.safeParse([
      { ...VALID_SOURCE, id: "cs000001-0000-4000-8000-000000000001" },
    ])
    expect(result.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// ArticleSchema
// ---------------------------------------------------------------------------

const VALID_ARTICLE = {
  id: "a1b2c3d4-0001-4000-8000-000000000001",
  title: "Pertamina Naikkan Harga BBM",
  url: "https://kompas.com/read/2025/05/01/bbm-naik",
  first_paragraph: "Pertamina resmi menaikkan harga BBM.",
  published_at: "2025-04-30T08:14:00",
  created_at: "2025-04-30T08:20:00",
  source_name: "Kompas",
  source_type: "rss",
}

describe("ArticleSchema", () => {
  test("accepts valid article payload", () => {
    expect(ArticleSchema.safeParse(VALID_ARTICLE).success).toBe(true)
  })

  test("accepts null first_paragraph", () => {
    expect(ArticleSchema.safeParse({ ...VALID_ARTICLE, first_paragraph: null }).success).toBe(true)
  })

  test("accepts null published_at", () => {
    expect(ArticleSchema.safeParse({ ...VALID_ARTICLE, published_at: null }).success).toBe(true)
  })

  test("accepts source_type 'internal'", () => {
    expect(ArticleSchema.safeParse({ ...VALID_ARTICLE, source_type: "internal" }).success).toBe(true)
  })

  test("rejects invalid source_type", () => {
    expect(ArticleSchema.safeParse({ ...VALID_ARTICLE, source_type: "trends" }).success).toBe(false)
  })

  test("rejects non-UUID id", () => {
    expect(ArticleSchema.safeParse({ ...VALID_ARTICLE, id: "mock-article-0001" }).success).toBe(false)
  })

  test("rejects missing created_at", () => {
    const { created_at: _omit, ...rest } = VALID_ARTICLE
    expect(ArticleSchema.safeParse(rest).success).toBe(false)
  })

  test("rejects missing source_name", () => {
    const { source_name: _omit, ...rest } = VALID_ARTICLE
    expect(ArticleSchema.safeParse(rest).success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// PaginatedArticlesSchema
// ---------------------------------------------------------------------------

describe("PaginatedArticlesSchema", () => {
  const VALID_PAGE = {
    items: [VALID_ARTICLE],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
  }

  test("accepts valid paginated response", () => {
    expect(PaginatedArticlesSchema.safeParse(VALID_PAGE).success).toBe(true)
  })

  test("accepts empty items array", () => {
    expect(PaginatedArticlesSchema.safeParse({ ...VALID_PAGE, items: [], total: 0 }).success).toBe(true)
  })

  test("rejects missing total_pages", () => {
    const { total_pages: _omit, ...rest } = VALID_PAGE
    expect(PaginatedArticlesSchema.safeParse(rest).success).toBe(false)
  })

  test("rejects non-integer total", () => {
    expect(PaginatedArticlesSchema.safeParse({ ...VALID_PAGE, total: 1.5 }).success).toBe(false)
  })

  test("rejects non-integer page", () => {
    expect(PaginatedArticlesSchema.safeParse({ ...VALID_PAGE, page: 1.5 }).success).toBe(false)
  })

  test("rejects article with invalid id inside items", () => {
    const result = PaginatedArticlesSchema.safeParse({
      ...VALID_PAGE,
      items: [{ ...VALID_ARTICLE, id: "mock-article-0000" }],
    })
    expect(result.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Fixture validation — morning-clusters + cluster details
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Fixture validation — bento + volume trend
// ---------------------------------------------------------------------------

describe("BentoListResponseSchema — bento-clusters fixture", () => {
  test("validates bento-clusters.json", () => {
    const result = BentoListResponseSchema.safeParse(bentoClusters)
    expect(result.success).toBe(true)
  })

  test("all 10 cards have required integer fields", () => {
    const result = BentoListResponseSchema.safeParse(bentoClusters)
    expect(result.success).toBe(true)
    if (!result.success) return
    for (const card of result.data.cards) {
      expect(typeof card.views).toBe("number")
      expect(typeof card.internal_article_count).toBe("number")
    }
  })
})

describe("VolumeTrendResponseSchema — cluster-volume-trend fixture", () => {
  test("validates cluster-volume-trend.json", () => {
    const result = VolumeTrendResponseSchema.safeParse(clusterVolumeTrend)
    expect(result.success).toBe(true)
  })

  test("fixture has exactly 48 hourly buckets", () => {
    const result = VolumeTrendResponseSchema.safeParse(clusterVolumeTrend)
    expect(result.success).toBe(true)
    if (!result.success) return
    expect(result.data.buckets.length).toBe(48)
    expect(result.data.bucket).toBe("hour")
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
