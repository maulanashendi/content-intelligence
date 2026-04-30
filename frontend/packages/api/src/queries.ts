// TanStack Query hooks consumed by feature views.
// useMorningClusters():    GET /api/v1/clusters/morning,  schema: ClusterListSchema
// useClusterDetail(id):    GET /api/v1/clusters/{id},     schema: ClusterDetailSchema
// useDeferredClusters():   GET /api/v1/clusters/deferred, schema: DeferredListSchema
// Defaults handled by QueryClient in @ei-fe/app/providers.tsx
// (staleTime 5min, gcTime 30min, refetchOnWindowFocus true, refetchInterval off).
