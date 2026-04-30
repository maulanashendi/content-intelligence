// MorningView — the 09:00 landing page for Maulana.
// Calls useMorningClusters().
// Renders:
//   - LoadingState (variant="table") while initial fetch
//   - ErrorState with retry on failure
//   - EmptyState if zero clusters returned
//   - <ClusterTable clusters={data} /> on success
// Top-10 sort by trend_velocity is BE-side; FE renders as-is.
// Row click → navigate to /clusters/:id (use react-router useNavigate).
