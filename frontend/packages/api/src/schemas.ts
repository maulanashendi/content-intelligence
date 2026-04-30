// Hand-written Zod schemas for runtime validation of API responses.
// Mirror generated.ts shape but enforce at runtime.
// Schemas:
//   ClusterSchema: id, label, member_count, competitor_count,
//     sample_headline, trend_velocity, novelty_score, coverage_score,
//     recommendation (enum), created_at (ISO).
//   ClusterListSchema: array of ClusterSchema.
//   ArticleMemberSchema: article_id, title, source_name, source_type,
//     url, published_at, first_paragraph, relevance_score.
//   ClusterDetailSchema: ClusterSchema fields + members: ArticleMemberSchema[].
//   DeferredClusterSchema: ClusterSchema fields + days_deferred (int).
//   DeferredListSchema: array of DeferredClusterSchema.
// Export inferred types for use in queries.ts and feature components.
