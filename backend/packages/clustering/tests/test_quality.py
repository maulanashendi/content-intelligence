import numpy as np
from clustering.quality import cluster_quality_signals


def test_signals_basic():
    labels = np.array([0, 0, 1, 1, 1, -1, -1])
    s = cluster_quality_signals(labels)
    assert s["n_articles"] == 7
    assert s["n_clusters"] == 2
    assert abs(s["noise_ratio"] - 2 / 7) < 1e-9
    assert abs(s["avg_cluster_size"] - 2.5) < 1e-9
    assert s["largest_cluster_size"] == 3


def test_signals_all_noise():
    labels = np.array([-1, -1, -1])
    s = cluster_quality_signals(labels)
    assert s["n_clusters"] == 0
    assert s["noise_ratio"] == 1.0
    assert s["avg_cluster_size"] == 0.0
    assert s["largest_cluster_size"] == 0


def test_signals_empty():
    s = cluster_quality_signals(np.array([], dtype=int))
    assert s["n_articles"] == 0
    assert s["noise_ratio"] == 0.0
