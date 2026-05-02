export const clusterKeys = {
  all: ["clusters"] as const,
  morning: () => [...clusterKeys.all, "morning"] as const,
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
