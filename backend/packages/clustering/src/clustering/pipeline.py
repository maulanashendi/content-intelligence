# Entry function: run() — full clustering pass.
# 1. Load embeddings from the last CLUSTERING_WINDOW_DAYS days.
# 2. UMAP reduce 768 -> 30 dims (random_state pinned for stability).
# 3. HDBSCAN cluster.
# 4. Set article_cluster.is_current = false on all previous-run rows.
# 5. Insert new cluster_run + article_cluster + article_cluster_member rows.
