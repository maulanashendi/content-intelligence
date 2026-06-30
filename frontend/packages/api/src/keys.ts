export const clusterKeys = {
  all: ["clusters"] as const,
  morning: (dna: boolean) => [...clusterKeys.all, "morning", dna] as const,
  current: (order: "asc" | "desc") => [...clusterKeys.all, "current", order] as const,
  detail: (id: string) => [...clusterKeys.all, "detail", id] as const,
  quadrantSummary: (dna: boolean) => [...clusterKeys.all, "quadrant-summary", dna] as const,
  byQuadrant: (quadrant: string, dna: boolean) => [...clusterKeys.all, "by-quadrant", quadrant, dna] as const,
  bento: (limit: number, dna: boolean) => [...clusterKeys.all, "bento", limit, dna] as const,
  volumeTrend: (id: string) => [...clusterKeys.all, "volume-trend", id] as const,
}

export const articleKeys = {
  all: ["articles"] as const,
  list: (page: number, pageSize: number) => [...articleKeys.all, "list", page, pageSize] as const,
  volumeTrend: (bucket: "hour" | "day") => [...articleKeys.all, "volume-trend", bucket] as const,
}

export const sourceKeys = {
  all: ["sources"] as const,
  list: () => [...sourceKeys.all, "list"] as const,
}

export const pipelineKeys = {
  all: ["pipeline"] as const,
  status: () => [...pipelineKeys.all, "status"] as const,
}

export const trendSignalKeys = {
  all: ["trend-signals"] as const,
  latest: (limit?: number) => [...trendSignalKeys.all, "latest", limit] as const,
}

export const clusterRunKeys = {
  all: ["cluster-runs"] as const,
  latest: () => [...clusterRunKeys.all, "latest"] as const,
}
