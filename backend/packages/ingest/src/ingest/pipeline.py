# Entry function: run() — performs full ingestion pass.
# 1. Fetch ~10 RSS sources in parallel via httpx + feedparser.
# 2. Parse Tempo internal sitemap.
# 3. Parse Google Trends RSS feeds.
# 4. Upsert articles with ON CONFLICT (url) DO NOTHING.
# 5. Upsert trend_signal + trend_signal_article rows in a transaction.
# 6. Update content_source.status to 'active' on success or 'error' on failure.
