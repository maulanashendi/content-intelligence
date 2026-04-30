# Entry function: run() — label every is_current cluster.
# 1. Iterate clusters where is_current = true.
# 2. For each cluster, pick top 3-5 articles by article_cluster_member.relevance_score.
# 3. Format prompt with title + first_paragraph.
# 4. Generate label with temperature=0 (reproducible within model version).
# 5. Update article_cluster.label.
