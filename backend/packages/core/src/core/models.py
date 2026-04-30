# SQLAlchemy ORM models — source of truth for Alembic autogenerate.
# Mirrors docs/schema.dbml. Tables:
#   - content_source           (rss | internal sources)
#   - article                  (unique on url)
#   - article_embedding        (vector(768), one row per article)
#   - article_gsc_metric       (reference-only, NEVER returned via API)
#   - cluster_run
#   - article_cluster          (centroid vector(768), is_current flag)
#   - article_cluster_member
#   - cluster_insight
#   - trend_signal             (Google Trends keyword + interest_score)
#   - trend_signal_article     (join: trend keyword <-> articles surfaced)
#
# Schema invariants (see docs/constraints.md):
#   - vector dimension is fixed at 768; switching model = migration + re-embed
#   - article_embedding.article_id is unique (one active embedding per article)
#   - source_type enum has only 'rss' and 'internal' (no 'trends')
