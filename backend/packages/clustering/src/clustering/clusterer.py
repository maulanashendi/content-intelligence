import hdbscan
import numpy as np
from core.config import settings


def cluster(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    clusterer = hdbscan.HDBSCAN(min_cluster_size=settings.hdbscan_min_cluster_size)
    clusterer.fit(vectors)
    return clusterer.labels_, clusterer.probabilities_
