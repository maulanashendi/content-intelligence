import sys

import pytest


def test_preflight_api_mode_imports_nothing(monkeypatch):
    from pipeline import runner

    monkeypatch.setattr(runner.settings, "embedding_provider", "api")
    monkeypatch.setattr(runner.settings, "labeling_provider", "api")
    # If pre-flight tried to import these, the None entries would raise ImportError.
    monkeypatch.setitem(sys.modules, "embedding.embedder", None)
    monkeypatch.setitem(sys.modules, "llama_cpp", None)

    runner._preflight_provider_deps()  # must not raise


def test_preflight_local_missing_dep_raises(monkeypatch):
    from pipeline import runner

    monkeypatch.setattr(runner.settings, "embedding_provider", "local")
    monkeypatch.setattr(runner.settings, "labeling_provider", "api")
    monkeypatch.setitem(sys.modules, "embedding.embedder", None)

    with pytest.raises(RuntimeError, match="pipeline-local"):
        runner._preflight_provider_deps()
