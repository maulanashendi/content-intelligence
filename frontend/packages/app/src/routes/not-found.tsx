import { Link } from "react-router-dom"
import { EmptyState, Button } from "@ei-fe/ui"

export function NotFoundRoute() {
  return (
    <div className="flex h-full items-center justify-center">
      <EmptyState
        title="Halaman tidak ditemukan"
        description="URL yang kamu kunjungi tidak ada."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link to="/morning">Kembali ke Morning Brief</Link>
          </Button>
        }
      />
    </div>
  )
}
