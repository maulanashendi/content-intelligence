// MSW handlers for the four API endpoints. Used by:
//   - @ei-fe/api/tests for client-level testing
//   - @ei-fe/features/tests for integration testing
// Handlers should:
//   - GET /api/v1/clusters/morning    → fixtures/morning-clusters.json
//   - GET /api/v1/clusters/:id        → fixtures/cluster-detail.json
//   - GET /api/v1/clusters/deferred   → fixtures/deferred-clusters.json
//   - GET /api/v1/health              → { status: "ok", db: true }
// Provide error variants (handlers500, handlersEmpty) for failure-state tests.
