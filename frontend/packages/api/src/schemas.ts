import { z } from "zod"

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
