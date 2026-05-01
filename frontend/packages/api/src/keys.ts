export const clusterKeys = {
  all: ["clusters"] as const,
  morning: () => [...clusterKeys.all, "morning"] as const,
  deferred: () => [...clusterKeys.all, "deferred"] as const,
  detail: (id: string) => [...clusterKeys.all, "detail", id] as const,
}
