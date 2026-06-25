from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    embedding_model_name: str = "google/embeddinggemma-300m"
    embedding_model_version: str = ""
    hf_home: str = "/models"
    hf_token: str = ""

    log_level: str = "INFO"
    log_dir: Path = Path("logs")

    analysis_window_days: int = 7
    clustering_window_days: int = 7
    scoring_trend_window_days: int = 7

    cluster_schedule_hour: int = 6
    cluster_schedule_minute: int = 0
    hdbscan_min_cluster_size: int = 5
    umap_random_state: int = 42
    umap_target_dimensions: int = 30

    cluster_merge_top_k: int = 3
    cluster_merge_similarity_threshold: float = 0.85
    cluster_split_min_avg_relevance: float = 0.6
    cluster_split_min_member_count: int = 10
    cluster_split_max_noise_ratio: float = 0.2

    ingest_timeout_seconds: int = 30
    scrape_fast_timeout_seconds: int = 10
    playwright_poll_interval_seconds: int = 120
    playwright_batch_size: int = 10
    timezone: str = "Asia/Jakarta"

    pipeline_lock_lease_ttl_seconds: int = 300
    pipeline_lock_heartbeat_seconds: int = 30
    cluster_scheduler_poll_seconds: int = 60
    source_error_backoff_seconds: int = 1800
    source_blocked_backoff_seconds: int = 3600

    gsc_site_url: str = "sc-domain:tempo.co"
    gsc_credentials_path: str = "teco-analytics-2cea1d43461c.json"
    gsc_fetch_days: int = 7

    # cluster_insight scoring (D27/D35)
    gsc_underperform_impressions_min: int = 100
    gsc_underperform_position_min: float = 10.0
    gsc_underperform_ctr_max: float = 0.02
    scoring_recent_internal_days: int = 7
    scoring_morning_top_n: int = 10
    scoring_deferred_velocity_min: float = 0.4
    cluster_staleness_max_age_hours: int = 36
    cluster_run_retention_count: int = 14
    # Demand and performance classification thresholds (percentile within current run).
    # Top (1 - percentile) fraction of clusters in the run are classified high.
    demand_high_percentile: float = 0.66
    performance_high_percentile: float = 0.66
    # When a run has more current clusters than this, label only the top N by
    # trend match (fresh signals, 24h) then member_count — cap the Gemma budget.
    labeling_max_clusters: int = 100
    # Labeling backend (SP2): "local" = Gemma; an llm preset name routes to API.
    labeling_provider: str = "local"
    labeling_model: str = "openai/gpt-4o-mini"
    labeling_llm_api_key: str = ""
    labeling_llm_base_url: str = ""
    labeling_request_timeout_seconds: float = 60.0
    labeling_attribution_referer: str = ""
    labeling_attribution_title: str = ""

    # Embedding backend (SP3): "local" = embeddinggemma (torch); "api" = OpenRouter embeddings.
    embedding_provider: str = "local"
    embedding_api_base_url: str = "https://openrouter.ai/api/v1"
    embedding_api_key: str = ""
    embedding_api_model: str = "openai/text-embedding-3-large"
    embedding_api_dimensions: int = 768
    embedding_request_timeout_seconds: float = 60.0
    embedding_attribution_referer: str = ""
    embedding_attribution_title: str = ""


settings = Settings()
