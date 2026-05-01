import { http, HttpResponse } from "msw"
import morningClusters from "./fixtures/morning-clusters.json"
import deferredClusters from "./fixtures/deferred-clusters.json"
import clusterDetail from "./fixtures/cluster-detail.json"

const BASE = "/api/v1"

export const handlers = [
  http.get(`${BASE}/clusters/morning`, () => HttpResponse.json(morningClusters)),
  http.get(`${BASE}/clusters/deferred`, () => HttpResponse.json(deferredClusters)),
  http.get(`${BASE}/clusters/:id`, ({ params }) => {
    const { id } = params
    if (id === clusterDetail.id) return HttpResponse.json(clusterDetail)
    return HttpResponse.json({ detail: "Not found" }, { status: 404 })
  }),
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
