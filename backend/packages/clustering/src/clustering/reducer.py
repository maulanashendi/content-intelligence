import numpy as np
import umap
from core.config import settings


def reduce(vectors: np.ndarray) -> np.ndarray:
    reducer = umap.UMAP(
        n_components=settings.umap_target_dimensions,
        random_state=settings.umap_random_state,
    )
    return reducer.fit_transform(vectors)
