import { useQuery } from "@tanstack/react-query"
import { apiGet } from "./client.js"
import { clusterKeys, articleKeys } from "./keys.js"
import { ClusterListSchema, ClusterDetailSchema, PaginatedArticlesSchema } from "./schemas.js"

export function useMorningClusters() {
  return useQuery({
    queryKey: clusterKeys.morning(),
    queryFn: () => apiGet("/clusters/morning", ClusterListSchema),
  })
}

export function useClusterDetail(id: string) {
  return useQuery({
    queryKey: clusterKeys.detail(id),
    queryFn: () => apiGet(`/clusters/${id}`, ClusterDetailSchema),
  })
}

export function clusterDetailQueryOptions(id: string) {
  return {
    queryKey: clusterKeys.detail(id),
    queryFn: () => apiGet(`/clusters/${id}`, ClusterDetailSchema),
  }
}

export function useArticles(page: number = 1, pageSize: number = 20) {
  return useQuery({
    queryKey: articleKeys.list(page, pageSize),
    queryFn: () => apiGet(`/articles?page=${page}&page_size=${pageSize}`, PaginatedArticlesSchema),
  })
}
