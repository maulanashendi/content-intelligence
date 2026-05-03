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
  label: z.string().nullable(),
  member_count: z.number().int().nullable(),
  trend_velocity: z.number().nullable(),
  novelty_score: z.number().nullable(),
  coverage_score: z.number().nullable(),
  recommendation: z.enum(["trending", "worth_writing", "saturated"]).nullable(),
})
export type ClusterSummary = z.infer<typeof ClusterSummarySchema>

export const ClusterListSchema = z.array(ClusterSummarySchema)
export type ClusterList = z.infer<typeof ClusterListSchema>

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

export const PipelineTriggerResultSchema = z.object({
  group: z.string(),
  channel: z.string(),
  notified: z.boolean(),
})
export type PipelineTriggerResult = z.infer<typeof PipelineTriggerResultSchema>

export const PipelineStatusSchema = z.object({
  ingest_embed: z.string().nullable(),
  cluster_label_score: z.string().nullable(),
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
