// Unit tests for src/client.ts.
// Cases:
//   - 2xx with valid shape → returns parsed data
//   - 2xx with shape that fails Zod → throws ApiError(status=200, message)
//   - 4xx → throws ApiError with response status
//   - 5xx → throws ApiError with response status
//   - Network failure → throws ApiError(status=0)
// Use MSW from tests/mocks/handlers.ts.
