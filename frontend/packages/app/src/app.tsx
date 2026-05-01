import { createBrowserRouter, RouterProvider, Navigate, Outlet } from "react-router-dom"
import { Sidebar, StatusBar } from "@ei-fe/ui"
import { MorningRoute } from "./routes/morning.js"
import { ArticleRoute } from "./routes/article.js"
import { ClusterDetailRoute } from "./routes/cluster-detail.js"
import { NotFoundRoute } from "./routes/not-found.js"
import { ClusteringRoute } from "./routes/clustering.js"
import { SourcesRoute } from "./routes/sources.js"
import { InputRssRoute } from "./routes/input-rss.js"

function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main">
        <StatusBar />
        <Outlet />
      </div>
    </div>
  )
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/morning" replace /> },
      { path: "morning", element: <MorningRoute /> },
      { path: "clusters/:id", element: <ClusterDetailRoute /> },
      { path: "article", element: <ArticleRoute /> },
      { path: "clustering", element: <ClusteringRoute /> },
      { path: "sources", element: <SourcesRoute /> },
      { path: "sources/rss", element: <InputRssRoute /> },
      { path: "*", element: <NotFoundRoute /> },
    ],
  },
])

export function App() {
  return <RouterProvider router={router} />
}
