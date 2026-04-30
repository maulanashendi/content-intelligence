from unittest.mock import MagicMock, patch

from labeling.llm import generate_label, get_llm


def test_generate_label_returns_string():
    llm = MagicMock()
    llm.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Lonjakan harga beras premium",
                }
            }
        ]
    }

    with patch("labeling.llm.get_llm", return_value=llm):
        label = generate_label(
            [
                {"title": "Harga beras naik", "first_paragraph": "Melonjak tajam."},
            ]
        )

    assert isinstance(label, str)
    assert len(label) > 0
    assert label == "Lonjakan harga beras premium"


def test_generate_label_strips_punctuation_and_newlines():
    llm = MagicMock()
    llm.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Harga beras premium terus naik.\nPenjelasan tambahan",
                }
            }
        ]
    }

    with patch("labeling.llm.get_llm", return_value=llm):
        label = generate_label(
            [
                {"title": "Test", "first_paragraph": "Test"},
            ]
        )

    assert label == "Harga beras premium terus naik"


def test_singleton_loaded_once():
    import labeling.llm as mod

    original_llm = mod._llm

    try:
        mod._llm = None

        mock_llama_class = MagicMock()
        mock_llm = MagicMock()
        mock_llama_class.from_pretrained.return_value = mock_llm

        with patch("labeling.llm._load_llama_class", return_value=mock_llama_class):
            llm1 = get_llm()
            llm2 = get_llm()

        assert llm1 is llm2
        mock_llama_class.from_pretrained.assert_called_once()
    finally:
        mod._llm = original_llm
