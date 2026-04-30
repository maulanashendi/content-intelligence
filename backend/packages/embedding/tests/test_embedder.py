from unittest.mock import MagicMock, patch

import embedding.embedder as embedder_module
from embedding.embedder import get_embedder


def test_singleton_reuse():
    original = embedder_module._model
    embedder_module._model = None
    try:
        mock_model = MagicMock()
        with patch("embedding.embedder.SentenceTransformer", return_value=mock_model):
            first = get_embedder()
            second = get_embedder()
        assert first is second
        assert first is mock_model
    finally:
        embedder_module._model = original
