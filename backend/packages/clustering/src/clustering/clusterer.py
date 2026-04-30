# HDBSCAN wrapper.
# min_cluster_size and min_samples loaded from core.config.
# Returns cluster_id per article plus relevance_score (probability output by HDBSCAN).
# Articles labeled as noise (cluster_id = -1) are skipped, not persisted.
