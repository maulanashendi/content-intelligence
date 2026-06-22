import { useSearchParams } from "react-router-dom"
import { AnalystView } from "@ei-fe/features"

export function AnalystRoute() {
  const [params] = useSearchParams()
  const title = params.get("title") ?? undefined
  return <AnalystView initialTitle={title} initialMode={title ? "analyze" : undefined} />
}
