// App shell.
// Renders Sidebar + main content area.
// Main contains StatusBar, PageHead (per-route), and <Outlet />.
// Routes wired here via createBrowserRouter:
//   /            → redirect to /morning
//   /morning     → MorningRoute
//   /clusters/:id → ClusterDetailRoute
//   /deferred    → DeferredRoute
//   *            → NotFoundRoute
