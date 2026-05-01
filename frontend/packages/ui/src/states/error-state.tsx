import { toUserMessage } from "@ei-fe/core"
import { AlertCircle } from "../icons.js"
import { Button } from "../primitives/button.js"

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <AlertCircle className="h-8 w-8 text-[color:var(--bad)]" />
      <p className="text-sm text-[color:var(--fg-muted)]">{toUserMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Coba lagi
        </Button>
      )}
    </div>
  )
}
