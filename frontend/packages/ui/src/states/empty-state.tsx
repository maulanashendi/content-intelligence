import type { ReactNode } from "react"
import { Inbox } from "../icons.js"

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <Inbox className="h-8 w-8 text-[color:var(--fg-ghost)]" />
      <div>
        <p className="text-sm font-medium text-[color:var(--fg)]">{title}</p>
        {description && <p className="mt-1 text-sm text-[color:var(--fg-muted)]">{description}</p>}
      </div>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
