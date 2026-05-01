import { useQuery } from "@tanstack/react-query"
import { apiGet } from "./client.js"
import { clusterKeys } from "./keys.js"
import { ClusterListSchema, ClusterDetailSchema } from "./schemas.js"

export function useMorningClusters() {
  return useQuery({
    queryKey: clusterKeys.morning(),
    queryFn: () => apiGet("/clusters/morning", ClusterListSchema),
  })
}

export function useDeferredClusters() {
  return useQuery({
    queryKey: clusterKeys.deferred(),
    queryFn: () => apiGet("/clusters/deferred", ClusterListSchema),
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
