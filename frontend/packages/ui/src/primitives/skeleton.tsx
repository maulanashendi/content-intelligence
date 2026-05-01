import { cn } from "../lib/cn.js"

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-[color:var(--bg-sunken)]", className)} />
}
