import { z } from "zod"

export const ArticleSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  url: z.string(),
  first_paragraph: z.string().nullable(),
  published_at: z.string().nullable(),
  created_at: z.string(),
  source_name: z.string(),
  source_type: z.enum(["rss", "internal"]),
})
export type Article = z.infer<typeof ArticleSchema>

export const PaginatedArticlesSchema = z.object({
  items: z.array(ArticleSchema),
  total: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
  total_pages: z.number().int(),
})
export type PaginatedArticles = z.infer<typeof PaginatedArticlesSchema>

export const ClusterSummarySchema = z.object({
  id: z.string().uuid(),
  parent_cluster_id: z.string().uuid().nullable(),
  label: z.string().nullable(),
  member_count: z.number().int().nullable(),
  is_current: z.boolean(),
  created_at: z.string().datetime(),
  trend_velocity: z.number().nullable(),
  competitor_count: z.number().int().nullable(),
  trend_match_count: z.number().int().nullable(),
  weighted_trend_score: z.number().nullable(),
  tempo_covered: z.boolean().nullable(),
  last_internal_days_ago: z.number().int().nullable(),
  underperformed: z.boolean().nullable(),
  competitor_freshness_days: z.number().int().nullable(),
  what_happened: z.string().nullable(),
  parties_involved: z.array(z.string()).nullable(),
  editorial_angle: z.string().nullable(),
  insight_calculated_at: z.string().datetime().nullable(),
})
export type ClusterSummary = z.infer<typeof ClusterSummarySchema>

export const ClusterListResponseSchema = z.object({
  clusters: z.array(ClusterSummarySchema),
  served_at: z.string().datetime().nullable(),
  is_stale: z.boolean(),
  max_age_hours: z.number().int(),
})
export type ClusterListResponse = z.infer<typeof ClusterListResponseSchema>

export const ArticleMemberSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  url: z.string(),
  first_paragraph: z.string().nullable(),
  published_at: z.string().nullable(),
  source_name: z.string(),
  relevance_score: z.number().nullable(),
})
export type ArticleMember = z.infer<typeof ArticleMemberSchema>

export const ClusterDetailSchema = ClusterSummarySchema.extend({
  members: z.array(ArticleMemberSchema),
  sub_clusters: z.array(ClusterSummarySchema).nullable(),
  is_stale: z.boolean(),
})
export type ClusterDetail = z.infer<typeof ClusterDetailSchema>

export const ContentSourceSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  url: z.string(),
  source_type: z.enum(["rss", "internal"]),
  is_enabled: z.boolean(),
  status: z.enum(["active", "error", "blocked"]).nullable(),
  last_fetched_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  article_count_24h: z.number().int(),
})
export type ContentSource = z.infer<typeof ContentSourceSchema>

export const ContentSourceListSchema = z.array(ContentSourceSchema)

export const SourceUpdateSchema = z.object({
  name: z.string().optional(),
  url: z.string().url().optional(),
  source_type: z.enum(["rss", "internal"]).optional(),
  is_enabled: z.boolean().optional(),
})
export type SourceUpdate = z.infer<typeof SourceUpdateSchema>

export const PipelineTriggerResultSchema = z.object({
  group: z.string(),
  channel: z.string(),
  notified: z.boolean(),
})
export type PipelineTriggerResult = z.infer<typeof PipelineTriggerResultSchema>

export const PipelineStatusSchema = z.object({
  cluster_label_score: z.string().nullable(),
  analysis: z.string().nullable(),
})
export type PipelineStatus = z.infer<typeof PipelineStatusSchema>

export const TrendSignalSchema = z.object({
  id: z.string().uuid(),
  keyword: z.string(),
  interest_score: z.number().nullable(),
  captured_at: z.string(),
  article_count: z.number().int(),
})
export type TrendSignal = z.infer<typeof TrendSignalSchema>

export const TrendSignalListSchema = z.array(TrendSignalSchema)

export const ClusterRunSchema = z.object({
  id: z.string().uuid(),
  algorithm: z.string().nullable(),
  algorithm_version: z.string().nullable(),
  params: z.record(z.unknown()).nullable(),
  started_at: z.string().datetime(),
  finished_at: z.string().datetime().nullable(),
  notes: z.string().nullable(),
  cluster_count: z.number().int(),
  has_insights: z.boolean(),
})
export type ClusterRun = z.infer<typeof ClusterRunSchema>
