from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_TASKS = frozenset({"analyze", "recommend"})


class AnalystSettings(BaseSettings):
    """Config for the Editorial AI Analyst.

    Vendor switch: set analyst_llm_provider to a preset name
    (openai | openrouter | ollama | vllm). base_url + headers come from the
    preset table in analyst/providers.py; analyst_llm_base_url overrides the
    preset base_url only for self-hosted endpoints whose host:port can't live
    in a static preset.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    analyst_llm_provider: str = "openai"
    analyst_llm_api_key: str = ""
    analyst_llm_base_url: str = ""
    analyst_request_timeout_seconds: float = 60.0
    analyst_attribution_referer: str = ""
    analyst_attribution_title: str = ""

    analyst_analyze_model: str = "gpt-4o"
    analyst_recommend_model: str = "gpt-4o"

    def model_for(self, task: str) -> str:
        if task not in _VALID_TASKS:
            raise ValueError(f"Unknown analyst task: {task!r}. Expected one of {sorted(_VALID_TASKS)}")
        return getattr(self, f"analyst_{task}_model")


settings = AnalystSettings()
