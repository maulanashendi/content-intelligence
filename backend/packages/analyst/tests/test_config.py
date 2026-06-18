from analyst.config import AnalystSettings


def test_defaults_and_per_task_resolution() -> None:
    s = AnalystSettings(_env_file=None)
    assert s.model_for("analyze") == "gpt-4o"
    assert s.model_for("recommend") == "gpt-4o"
    # falls back to the shared base url when no per-task override is set
    assert s.base_url_for("analyze") == "https://api.openai.com/v1"


def test_per_task_base_url_override() -> None:
    s = AnalystSettings(
        _env_file=None,
        analyst_recommend_base_url="http://localhost:11434/v1",
    )
    assert s.base_url_for("recommend") == "http://localhost:11434/v1"
    assert s.base_url_for("analyze") == "https://api.openai.com/v1"
