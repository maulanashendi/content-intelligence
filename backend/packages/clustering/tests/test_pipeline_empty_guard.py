import logging
from unittest.mock import AsyncMock

import numpy as np

from clustering import pipeline


def _patch_leaves(monkeypatch, labels: np.ndarray) -> AsyncMock:
    """Stub the DB + native calls so run() reaches the persist decision deterministically."""
    embeddings = np.ones((len(labels), 4), dtype=np.float32)
    probs = np.ones(len(labels), dtype=np.float32)

    monkeypatch.setattr(
        pipeline, "_load_recent_embeddings",
        AsyncMock(return_value=(embeddings, [f"id-{i}" for i in range(len(labels))])),
    )
    monkeypatch.setattr(pipeline, "umap_reduce", lambda e: e)
    monkeypatch.setattr(pipeline, "hdbscan_cluster", lambda r: (labels, probs))
    monkeypatch.setattr(pipeline, "merge_run", AsyncMock(return_value=0))
    monkeypatch.setattr(pipeline, "split_run", AsyncMock(return_value=0))

    persist = AsyncMock()
    monkeypatch.setattr(pipeline, "_persist_clusters", persist)
    return persist


async def test_run_skips_persist_when_only_noise(monkeypatch, caplog) -> None:
    persist = _patch_leaves(monkeypatch, np.array([-1, -1, -1]))

    with caplog.at_level(logging.WARNING, logger=pipeline.logger.name):
        await pipeline.run()

    persist.assert_not_awaited()
    assert any("only noise" in r.message for r in caplog.records)


async def test_run_persists_when_real_cluster_found(monkeypatch) -> None:
    persist = _patch_leaves(monkeypatch, np.array([0, 0, -1]))

    await pipeline.run()

    persist.assert_awaited_once()
