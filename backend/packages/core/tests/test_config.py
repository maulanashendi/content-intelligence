def test_provider_defaults_are_api(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("LABELING_PROVIDER", raising=False)
    from core.config import Settings

    s = Settings(database_url="postgresql+asyncpg://x:x@localhost/x", _env_file=None)
    assert s.embedding_provider == "api"
    assert s.labeling_provider == "api"


def test_morning_filter_defaults():
    from core.config import Settings

    s = Settings(database_url="postgresql+asyncpg://x:x@localhost/x", _env_file=None)
    assert "Politik" in s.morning_allowed_desks
    assert "Hiburan" not in s.morning_allowed_desks
    assert "Divert me" in s.morning_denied_user_needs
    assert "Keep me engaged" in s.morning_denied_user_needs
