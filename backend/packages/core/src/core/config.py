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

    clustering_window_days: int = 7

    cluster_schedule_hour: int = 6
    cluster_schedule_minute: int = 0
    hdbscan_min_cluster_size: int = 5
    umap_random_state: int = 42
    umap_target_dimensions: int = 30

    ingest_timeout_seconds: int = 30
    scrape_fast_timeout_seconds: int = 10
    playwright_poll_interval_seconds: int = 120
    playwright_batch_size: int = 10
    timezone: str = "Asia/Jakarta"

    gsc_site_url: str = "sc-domain:tempo.co"
    gsc_credentials_path: str = "teco-analytics-2cea1d43461c.json"
    gsc_fetch_days: int = 7

    # cluster_insight scoring (D27)
    gsc_underperform_impressions_min: int = 100
    gsc_underperform_position_min: float = 10.0
    gsc_underperform_ctr_max: float = 0.02
    scoring_recent_internal_days: int = 7
    scoring_morning_top_n: int = 10
    scoring_deferred_velocity_min: float = 0.4


settings = Settings()
