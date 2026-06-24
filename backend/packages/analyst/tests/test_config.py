import pytest

from analyst.config import AnalystSettings


def test_defaults() -> None:
    s = AnalystSettings(_env_file=None)
    assert s.analyst_llm_provider == "openai"
    assert s.analyst_llm_base_url == ""
    assert s.analyst_llm_api_key == ""
    assert s.analyst_request_timeout_seconds == 60.0
    assert s.model_for("analyze") == "gpt-4o"
    assert s.model_for("recommend") == "gpt-4o"


def test_model_for_rejects_unknown_task() -> None:
    s = AnalystSettings(_env_file=None)
    with pytest.raises(ValueError, match="Unknown analyst task"):
        s.model_for("translate")


def test_per_task_base_url_is_gone() -> None:
    s = AnalystSettings(_env_file=None)
    assert not hasattr(s, "base_url_for")
    assert not hasattr(s, "analyst_analyze_base_url")
