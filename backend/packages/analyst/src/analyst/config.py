from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_TASKS = frozenset({"analyze", "recommend"})


class AnalystSettings(BaseSettings):
    """Config for the Editorial AI Analyst.

    'local' vs 'API' is a base-URL swap: point a task's *_base_url at a local
    OpenAI-compatible server (Ollama/llama.cpp/vLLM) or a hosted endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    analyst_llm_base_url: str = "https://api.openai.com/v1"
    analyst_llm_api_key: str = ""
    analyst_request_timeout_seconds: float = 60.0

    analyst_analyze_model: str = "gpt-4o"
    analyst_analyze_base_url: str = ""
    analyst_recommend_model: str = "gpt-4o"
    analyst_recommend_base_url: str = ""

    def model_for(self, task: str) -> str:
        if task not in _VALID_TASKS:
            raise ValueError(f"Unknown analyst task: {task!r}. Expected one of {sorted(_VALID_TASKS)}")
        return getattr(self, f"analyst_{task}_model")

    def base_url_for(self, task: str) -> str:
        if task not in _VALID_TASKS:
            raise ValueError(f"Unknown analyst task: {task!r}. Expected one of {sorted(_VALID_TASKS)}")
        override: str = getattr(self, f"analyst_{task}_base_url")
        return override or self.analyst_llm_base_url


settings = AnalystSettings()
