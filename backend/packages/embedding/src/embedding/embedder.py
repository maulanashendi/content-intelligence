# Singleton embedder.
# Loads google/embeddinggemma-300m once via sentence-transformers and reuses
# the model across all batch calls within a pipeline run.
# Switching models requires schema migration + re-embed (see docs/decisions.md D4).
