# Google Trends RSS ingestion.
# Persists keyword + interest_score to trend_signal.
# Articles surfaced under each trend go to article (source_id = real outlet
# such as detik/kompas, NOT a virtual 'trends' source).
# trend_signal_article links the keyword to its surfaced articles.
# All three writes happen in one transaction.
