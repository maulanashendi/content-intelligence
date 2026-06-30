import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query"
import { apiDelete, apiGet, apiPatch, apiPost } from "./client.js"
import { clusterKeys, articleKeys, sourceKeys, pipelineKeys, trendSignalKeys, clusterRunKeys } from "./keys.js"
import { ClusterListResponseSchema, ClusterDetailSchema, PaginatedArticlesSchema, ContentSourceSchema, ContentSourceListSchema, PipelineTriggerResultSchema, PipelineStatusSchema, TrendSignalListSchema, ClusterRunSchema, QuadrantSummarySchema, AnalyzeResultSchema, RecommendationOutputSchema, VolumeTrendResponseSchema, BentoListResponseSchema } from "./schemas.js"
import type { SourceUpdate } from "./schemas.js"

export function useMorningClusters(dna: boolean = true) {
  return useQuery({
    queryKey: clusterKeys.morning(dna),
    queryFn: () => apiGet(`/clusters/morning?dna=${dna}`, ClusterListResponseSchema),
  })
}

export function useCurrentClusters(order: "asc" | "desc" = "desc", enabled: boolean = true) {
  return useQuery({
    queryKey: clusterKeys.current(order),
    queryFn: () => apiGet(`/clusters/current?order=${order}`, ClusterListResponseSchema),
    enabled,
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

export function useSources() {
  return useQuery({
    queryKey: sourceKeys.list(),
    queryFn: () => apiGet("/sources", ContentSourceListSchema),
  })
}

export function useCreateSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { url: string; name: string; is_enabled: boolean }) =>
      apiPost("/sources", body, ContentSourceSchema),
    onSuccess: () => qc.invalidateQueries({ queryKey: sourceKeys.list() }),
  })
}

export function useDeleteSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/sources/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: sourceKeys.list() }),
  })
}

export function usePipelineStatus(refetchInterval: number | false = false) {
  return useQuery({
    queryKey: pipelineKeys.status(),
    queryFn: () => apiGet("/pipeline/status", PipelineStatusSchema),
    refetchInterval,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  })
}

export function useTriggerClusterLabelScore() {
  return useMutation({
    mutationFn: () => apiPost("/pipeline/cluster-label-score", {}, PipelineTriggerResultSchema),
  })
}

export function useTriggerAnalysis() {
  return useMutation({
    mutationFn: () => apiPost("/pipeline/analysis", {}, PipelineTriggerResultSchema),
  })
}

export function useTrendSignals(limit: number = 10) {
  return useQuery({
    queryKey: trendSignalKeys.latest(limit),
    queryFn: () => apiGet(`/trend-signals/latest?limit=${limit}`, TrendSignalListSchema),
  })
}

export function useQuadrantSummary(dna: boolean = true) {
  return useQuery({
    queryKey: clusterKeys.quadrantSummary(dna),
    queryFn: () => apiGet(`/clusters/quadrant-summary?dna=${dna}`, QuadrantSummarySchema),
    staleTime: 5 * 60 * 1000,
  })
}

export function useClustersByQuadrant(quadrant: string | null, limit = 8, dna: boolean = true) {
  return useQuery({
    queryKey: clusterKeys.byQuadrant(quadrant ?? "", dna),
    queryFn: () => apiGet(`/clusters/quadrant/${quadrant}?limit=${limit}&dna=${dna}`, ClusterListResponseSchema),
    enabled: !!quadrant,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLatestClusterRun() {
  return useQuery({
    queryKey: clusterRunKeys.latest(),
    queryFn: () => apiGet("/clusters/runs/latest", ClusterRunSchema),
  })
}

export function useUpdateSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SourceUpdate }) =>
      apiPatch(`/sources/${id}`, data, ContentSourceSchema),
    onSuccess: () => qc.invalidateQueries({ queryKey: sourceKeys.list() }),
  })
}

export function useToggleSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      apiPatch(`/sources/${id}`, { is_enabled }, ContentSourceSchema),
    onMutate: async ({ id, is_enabled }) => {
      await qc.cancelQueries({ queryKey: sourceKeys.list() })
      const prev = qc.getQueryData(sourceKeys.list())
      qc.setQueryData(sourceKeys.list(), (old: unknown) => {
        if (!Array.isArray(old)) return old
        return old.map((s: { id: string; is_enabled: boolean }) =>
          s.id === id ? { ...s, is_enabled } : s,
        )
      })
      return { prev }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev !== undefined) qc.setQueryData(sourceKeys.list(), ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: sourceKeys.list() }),
  })
}

export function useAnalyzeArticle() {
  return useMutation({
    mutationFn: (body: { title: string; content: string }) =>
      apiPost("/analyst/analyze", body, AnalyzeResultSchema),
  })
}

export function useRecommendation() {
  return useMutation({
    mutationFn: (intent: string) =>
      apiPost("/analyst/recommendation", { intent }, RecommendationOutputSchema),
  })
}

export function useVolumeTrend(bucket: "hour" | "day") {
  return useQuery({
    queryKey: articleKeys.volumeTrend(bucket),
    queryFn: () => apiGet(`/articles/volume-trend?bucket=${bucket}`, VolumeTrendResponseSchema),
    staleTime: 5 * 60 * 1000,
  })
}

// Growing-limit pagination by design: "Show more" increments limit (8→16→24…) and re-fetches the
// full window from offset=0. offset is hardcoded and NOT in the query key; add it there before
// converting to true offset paging.
export function useClusterBento(limit: number, dna: boolean = true) {
  return useQuery({
    queryKey: clusterKeys.bento(limit, dna),
    queryFn: () => apiGet(`/clusters/bento?limit=${limit}&offset=0&dna=${dna}`, BentoListResponseSchema),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
  })
}

export function useClusterVolumeTrend(id: string, enabled: boolean) {
  return useQuery({
    queryKey: clusterKeys.volumeTrend(id),
    queryFn: () => apiGet(`/clusters/${id}/volume-trend?bucket=hour`, VolumeTrendResponseSchema),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}
