import { useParams, Link } from "react-router-dom"
import { PageHead } from "@ei-fe/ui"
import { ClusterDetailView } from "@ei-fe/features"

export function ClusterDetailRoute() {
  const { id } = useParams<{ id: string }>()
  if (!id) return null
  return (
    <>
      <PageHead
        title="Detail Cluster"
        back={
          <Link
            to="/morning"
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: "3px 8px" }}
          >
            ← Morning Brief
          </Link>
        }
      />
      <ClusterDetailView id={id} />
    </>
  )
}
