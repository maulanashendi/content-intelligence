import os

from core.config import settings
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        os.environ.setdefault("HF_HOME", settings.hf_home)
        _model = SentenceTransformer(
            settings.embedding_model_name,
            trust_remote_code=True,  # required by google/embeddinggemma-300m custom pooling code
        )
    return _model
