import sys

import pytest


@pytest.mark.asyncio
async def test_encode_local_missing_extra_raises_actionable(monkeypatch):
    import embedding.pipeline as ep

    monkeypatch.setattr(ep.settings, "embedding_provider", "local")
    # Simulate the local extra being absent: importing embedding.embedder fails.
    monkeypatch.setitem(sys.modules, "embedding.embedder", None)

    with pytest.raises(RuntimeError, match="pipeline-local"):
        await ep._encode(["hello world"])
