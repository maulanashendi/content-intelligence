// Route file for /clusters/:id.
// Reads :id from useParams.
// Renders <PageHead .../> + <ClusterDetailView clusterId={id} />.
// 404 cluster is handled INSIDE ClusterDetailView (EmptyState),
// not by router-level error boundary.
