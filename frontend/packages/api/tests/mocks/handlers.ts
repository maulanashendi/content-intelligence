import { http, HttpResponse } from "msw"
import morningClusters from "./fixtures/morning-clusters.json"
import deferredClusters from "./fixtures/deferred-clusters.json"
import clusterDetail from "./fixtures/cluster-detail.json"
import sources from "./fixtures/sources.json"
import articles from "./fixtures/articles.json"

const BASE = "/api/v1"

export const handlers = [
  http.get(`${BASE}/clusters/morning`, () => HttpResponse.json(morningClusters)),
  http.get(`${BASE}/clusters/deferred`, () => HttpResponse.json(deferredClusters)),
  http.get(`${BASE}/clusters/:id`, ({ params }) => {
    const { id } = params
    if (id === clusterDetail.id) return HttpResponse.json(clusterDetail)
    return HttpResponse.json({ detail: "Not found" }, { status: 404 })
  }),
  http.get(`${BASE}/articles`, () => HttpResponse.json(articles)),
  http.get(`${BASE}/sources`, () => HttpResponse.json(sources)),
  http.post(`${BASE}/sources`, () =>
    HttpResponse.json({ ...sources[0], id: "f47ac10b-58cc-4372-a567-0e02b2c3d479" }, { status: 201 }),
  ),
  http.delete(`${BASE}/sources/:id`, () => new HttpResponse(null, { status: 204 })),
  http.patch(`${BASE}/sources/:id`, () => HttpResponse.json({ ...sources[0], is_enabled: false })),
  http.get(`${BASE}/health`, () => HttpResponse.json({ status: "ok", db: true })),
]

export const handlers500 = [
  http.get(`${BASE}/clusters/morning`, () => HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 })),
  http.get(`${BASE}/clusters/deferred`, () => HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 })),
  http.get(`${BASE}/clusters/:id`, () => HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 })),
]

export const handlersEmpty = [
  http.get(`${BASE}/clusters/morning`, () => HttpResponse.json([])),
  http.get(`${BASE}/clusters/deferred`, () => HttpResponse.json([])),
]
