import { Skeleton } from "../primitives/skeleton.js"

interface LoadingStateProps {
  variant: "table" | "detail"
  rows?: number
}

export function LoadingState({ variant, rows = 10 }: LoadingStateProps) {
  if (variant === "table") {
    return (
      <div className="px-6 py-4 space-y-2">
        <Skeleton className="h-8 w-full" />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    )
  }
  return (
    <div className="px-6 py-6 space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-1/3" />
        <Skeleton className="h-5 w-1/4" />
        <div className="flex gap-4 pt-2">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-20" />
        </div>
      </div>
      <div className="space-y-2">
        <Skeleton className="h-8 w-full" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  )
}
