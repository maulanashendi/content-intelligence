# Entry function: run() — score every is_current cluster.
# 1. For each cluster: compute velocity, novelty, coverage.
# 2. Derive recommendation enum (trending | worth_writing | saturated) from thresholds.
# 3. Insert cluster_insight row.
