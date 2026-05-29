import { describe, test, expect, mock, beforeEach } from "bun:test"
import { apiGet, apiPost, apiPatch, apiDelete } from "../src/client.js"
import { ContentSourceListSchema, ContentSourceSchema, ClusterListResponseSchema, PaginatedArticlesSchema } from "../src/schemas.js"
import { ApiError } from "@ei-fe/core"

function mockFetch(body: unknown, status = 200) {
  const res = new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
  globalThis.fetch = mock(() => Promise.resolve(res))
}

function mockFetchNetworkError() {
  globalThis.fetch = mock(() => Promise.reject(new TypeError("network error")))
}

beforeEach(() => {
  // Reset to real fetch before each test so leaks don't cross tests.
  globalThis.fetch = globalThis.fetch
})

// ---------------------------------------------------------------------------
// GET /sources — the bug that caused "Respons API tidak sesuai skema"
// ---------------------------------------------------------------------------

describe("apiGet /sources — schema validation", () => {
  test("returns parsed list when backend returns valid UUIDs", async () => {
    mockFetch([
      {
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
      },
    ])
    const data = await apiGet("/sources", ContentSourceListSchema)
    expect(data).toHaveLength(1)
    expect(data[0].name).toBe("Kompas RSS")
  })

  test("throws ApiError 'tidak sesuai skema' when id contains non-hex chars like 'cs000001-...'", async () => {
    // Root cause: MSW mock used "cs000001-0000-4000-8000-000000000001" — 's' is not a
    // hex digit so z.string().uuid() rejects it, producing "Respons API tidak sesuai skema."
    mockFetch([
      {
        id: "cs000001-0000-4000-8000-000000000001",
        name: "Bad Mock",
        url: "https://example.com/rss",
        source_type: "rss",
        is_enabled: true,
        status: null,
        last_fetched_at: null,
        created_at: "2025-11-01T00:00:00",
        updated_at: "2025-11-01T00:00:00",
        article_count_24h: 0,
      },
    ])
    await expect(apiGet("/sources", ContentSourceListSchema)).rejects.toMatchObject({
      message: "Respons API tidak sesuai skema.",
    })
  })

  test("throws ApiError 'tidak sesuai skema' when source_type is 'api' (not in schema enum)", async () => {
    mockFetch([
      {
        id: "a1b2c3d4-0001-4000-8000-000000000001",
        name: "Bisnis API",
        url: "https://api.bisnis.com/v2",
        source_type: "api",
        is_enabled: true,
        status: null,
        last_fetched_at: null,
        created_at: "2025-11-01T00:00:00",
        updated_at: "2025-11-01T00:00:00",
        article_count_24h: 0,
      },
    ])
    await expect(apiGet("/sources", ContentSourceListSchema)).rejects.toMatchObject({
      message: "Respons API tidak sesuai skema.",
    })
  })

  test("returns empty array on 200 []", async () => {
    mockFetch([])
    const data = await apiGet("/sources", ContentSourceListSchema)
    expect(data).toHaveLength(0)
  })

  test("throws ApiError with HTTP status on 500", async () => {
    mockFetch({ detail: "Internal Server Error" }, 500)
    await expect(apiGet("/sources", ContentSourceListSchema)).rejects.toMatchObject({ status: 500 })
  })
})

// ---------------------------------------------------------------------------
// POST /sources
// ---------------------------------------------------------------------------

describe("apiPost /sources", () => {
  const newSource = {
    id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    name: "Kompas RSS",
    url: "https://rss.kompas.com/nasional",
    source_type: "rss",
    is_enabled: true,
    status: null,
    last_fetched_at: null,
    created_at: "2026-05-01T00:00:00",
    updated_at: "2026-05-01T00:00:00",
    article_count_24h: 0,
  }

  test("returns created source on 201", async () => {
    mockFetch(newSource, 201)
    const data = await apiPost("/sources", { url: newSource.url, name: newSource.name, is_enabled: true }, ContentSourceSchema)
    expect(data.id).toBe(newSource.id)
    expect(data.source_type).toBe("rss")
  })

  test("throws ApiError(409) when URL already exists", async () => {
    mockFetch({ detail: "URL sudah terdaftar." }, 409)
    await expect(
      apiPost("/sources", { url: "https://rss.kompas.com/nasional", name: "", is_enabled: true }, ContentSourceSchema),
    ).rejects.toMatchObject({ status: 409, message: "URL sudah terdaftar." })
  })

  test("throws ApiError(422) on invalid body", async () => {
    mockFetch({ detail: "URL tidak valid." }, 422)
    await expect(
      apiPost("/sources", { url: "not-a-url", name: "", is_enabled: true }, ContentSourceSchema),
    ).rejects.toMatchObject({ status: 422 })
  })
})

// ---------------------------------------------------------------------------
// PATCH /sources/:id
// ---------------------------------------------------------------------------

describe("apiPatch /sources/:id", () => {
  const updated = {
    id: "a1b2c3d4-0001-4000-8000-000000000001",
    name: "Kompas RSS",
    url: "https://rss.kompas.com/nasional",
    source_type: "rss",
    is_enabled: false,
    status: "active",
    last_fetched_at: "2026-04-30T06:12:00",
    created_at: "2025-11-01T00:00:00",
    updated_at: "2026-05-01T00:00:00",
    article_count_24h: 142,
  }

  test("returns source with toggled is_enabled", async () => {
    mockFetch(updated)
    const data = await apiPatch("/sources/a1b2c3d4-0001-4000-8000-000000000001", { is_enabled: false }, ContentSourceSchema)
    expect(data.is_enabled).toBe(false)
  })

  test("throws ApiError(404) when source not found", async () => {
    mockFetch({ detail: "Source tidak ditemukan." }, 404)
    await expect(
      apiPatch("/sources/00000000-0000-0000-0000-000000000000", { is_enabled: true }, ContentSourceSchema),
    ).rejects.toMatchObject({ status: 404, message: "Source tidak ditemukan." })
  })
})

// ---------------------------------------------------------------------------
// DELETE /sources/:id
// ---------------------------------------------------------------------------

describe("apiDelete /sources/:id", () => {
  test("resolves undefined on 204", async () => {
    globalThis.fetch = mock(() => Promise.resolve(new Response(null, { status: 204 })))
    await expect(apiDelete("/sources/a1b2c3d4-0001-4000-8000-000000000001")).resolves.toBeUndefined()
  })

  test("throws ApiError(409) when source has articles", async () => {
    mockFetch({ detail: "Sumber memiliki artikel dan tidak dapat dihapus." }, 409)
    await expect(apiDelete("/sources/a1b2c3d4-0001-4000-8000-000000000001")).rejects.toMatchObject({
      status: 409,
      message: "Sumber memiliki artikel dan tidak dapat dihapus.",
    })
  })

  test("throws ApiError(404) when source not found", async () => {
    mockFetch({ detail: "Source tidak ditemukan." }, 404)
    await expect(apiDelete("/sources/00000000-0000-0000-0000-000000000000")).rejects.toMatchObject({ status: 404 })
  })
})

// ---------------------------------------------------------------------------
// GET /articles — paginated article list
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

describe("apiGet /articles — schema validation", () => {
  test("returns parsed paginated response on 200", async () => {
    mockFetch({ items: [VALID_ARTICLE], total: 1, page: 1, page_size: 20, total_pages: 1 })
    const data = await apiGet("/articles?page=1&page_size=20", PaginatedArticlesSchema)
    expect(data.total).toBe(1)
    expect(data.items).toHaveLength(1)
    expect(data.items[0]!.title).toBe("Pertamina Naikkan Harga BBM")
    expect(data.items[0]!.source_type).toBe("rss")
  })

  test("returns empty items on 200 with zero articles", async () => {
    mockFetch({ items: [], total: 0, page: 1, page_size: 20, total_pages: 1 })
    const data = await apiGet("/articles?page=1&page_size=20", PaginatedArticlesSchema)
    expect(data.items).toHaveLength(0)
    expect(data.total).toBe(0)
  })

  test("parses article with null first_paragraph and null published_at", async () => {
    mockFetch({
      items: [{ ...VALID_ARTICLE, first_paragraph: null, published_at: null }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    })
    const data = await apiGet("/articles", PaginatedArticlesSchema)
    expect(data.items[0]!.first_paragraph).toBeNull()
    expect(data.items[0]!.published_at).toBeNull()
  })

  test("parses article with source_type 'internal'", async () => {
    mockFetch({
      items: [{ ...VALID_ARTICLE, source_type: "internal" }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    })
    const data = await apiGet("/articles", PaginatedArticlesSchema)
    expect(data.items[0]!.source_type).toBe("internal")
  })

  test("throws ApiError 'tidak sesuai skema' when article id is not a UUID", async () => {
    mockFetch({
      items: [{ ...VALID_ARTICLE, id: "mock-article-0001" }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    })
    await expect(apiGet("/articles", PaginatedArticlesSchema)).rejects.toMatchObject({
      message: "Respons API tidak sesuai skema.",
    })
  })

  test("throws ApiError 'tidak sesuai skema' when source_type is unknown value", async () => {
    mockFetch({
      items: [{ ...VALID_ARTICLE, source_type: "trends" }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    })
    await expect(apiGet("/articles", PaginatedArticlesSchema)).rejects.toMatchObject({
      message: "Respons API tidak sesuai skema.",
    })
  })

  test("throws ApiError 'tidak sesuai skema' when pagination fields are missing", async () => {
    mockFetch({ items: [VALID_ARTICLE], total: 1, page: 1 })
    await expect(apiGet("/articles", PaginatedArticlesSchema)).rejects.toMatchObject({
      message: "Respons API tidak sesuai skema.",
    })
  })

  test("throws ApiError(500) on server error", async () => {
    mockFetch({ detail: "Internal Server Error" }, 500)
    await expect(apiGet("/articles", PaginatedArticlesSchema)).rejects.toMatchObject({ status: 500 })
  })
})

// ---------------------------------------------------------------------------
// Generic apiGet — existing error paths
// ---------------------------------------------------------------------------

describe("apiGet — generic error paths", () => {
  test("throws ApiError(500) on server error", async () => {
    mockFetch({ detail: "Internal Server Error" }, 500)
    await expect(apiGet("/clusters/morning", ClusterListResponseSchema)).rejects.toMatchObject({ status: 500 })
  })

  test("includes detail message from response body", async () => {
    mockFetch({ detail: "Cluster not found" }, 404)
    const err = await apiGet("/clusters/abc", ClusterListResponseSchema).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe("Cluster not found")
  })
})
