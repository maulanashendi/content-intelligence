import numpy as np


def cluster_quality_signals(labels) -> dict[str, float]:
    labels = np.asarray(labels)
    total = int(labels.shape[0])
    if total == 0:
        return {
            "n_articles": 0,
            "n_clusters": 0,
            "noise_ratio": 0.0,
            "avg_cluster_size": 0.0,
            "largest_cluster_size": 0,
        }
    noise = int((labels == -1).sum())
    cluster_ids = sorted(set(labels.tolist()) - {-1})
    sizes = [int((labels == cid).sum()) for cid in cluster_ids]
    return {
        "n_articles": total,
        "n_clusters": len(cluster_ids),
        "noise_ratio": noise / total,
        "avg_cluster_size": (sum(sizes) / len(sizes)) if sizes else 0.0,
        "largest_cluster_size": max(sizes) if sizes else 0,
    }
