export const clusterKeys = {
  all: ["clusters"] as const,
  morning: () => [...clusterKeys.all, "morning"] as const,
  current: (order: "asc" | "desc") => [...clusterKeys.all, "current", order] as const,
  detail: (id: string) => [...clusterKeys.all, "detail", id] as const,
}

export const articleKeys = {
  all: ["articles"] as const,
  list: (page: number, pageSize: number) => [...articleKeys.all, "list", page, pageSize] as const,
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
