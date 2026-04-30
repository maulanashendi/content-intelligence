# Competitor RSS parsing (detik, kompas, tirto, cnnindonesia, kontan, etc.).
# Async parallel fetch via httpx; parsing via feedparser.
# Each successful row is upserted into article with source_type='rss'.
