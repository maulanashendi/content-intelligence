from core.config import Settings


def test_labeling_defaults() -> None:
    s = Settings(_env_file=None, database_url="postgresql+asyncpg://x:y@localhost/z")
    assert s.labeling_provider == "api"
    assert s.labeling_model == "openai/gpt-4o-mini"
    assert s.labeling_llm_api_key == ""
    assert s.labeling_request_timeout_seconds == 60.0
