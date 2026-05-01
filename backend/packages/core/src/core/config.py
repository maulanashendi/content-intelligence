from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    embedding_model_name: str = "google/embeddinggemma-300m"
    embedding_model_version: str = ""
    hf_home: str = "/models"

    log_level: str = "INFO"
    log_dir: Path = Path("logs")

    clustering_window_days: int = 30
    hdbscan_min_cluster_size: int = 5
    umap_random_state: int = 42
    umap_target_dimensions: int = 30

    ingest_timeout_seconds: int = 30
    timezone: str = "Asia/Jakarta"


settings = Settings()
