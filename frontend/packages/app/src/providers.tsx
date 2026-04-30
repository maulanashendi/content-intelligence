// Providers wrapping the entire app.
// QueryClientProvider with config from frontend.md §"Data layer":
//   staleTime: 5 * 60_000
//   gcTime:    30 * 60_000
//   refetchOnWindowFocus: true
//   refetchOnMount: true
//   retry: 3
//   refetchInterval: undefined
// RouterProvider for react-router-dom data router.
// Optional: TanStack Query Devtools in dev only.
