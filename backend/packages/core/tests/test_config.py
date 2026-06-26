def test_provider_defaults_are_api(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("LABELING_PROVIDER", raising=False)
    from core.config import Settings

    s = Settings(database_url="postgresql+asyncpg://x:x@localhost/x", _env_file=None)
    assert s.embedding_provider == "api"
    assert s.labeling_provider == "api"
