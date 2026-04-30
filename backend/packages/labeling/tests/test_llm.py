from unittest.mock import MagicMock, patch

import torch
from labeling.llm import generate_label, get_model_and_tokenizer


class _FakeBatchEncoding(dict):
    def to(self, device):
        return self


def _mock_model_and_tokenizers():
    model = MagicMock()
    model.device = torch.device("cpu")

    input_ids = torch.tensor([[1, 2, 3]])
    fake_output = torch.tensor([[1, 2, 3, 101, 202, 203]])
    model.generate.return_value = fake_output

    tokenizer = MagicMock()
    tokenizer.apply_chat_template.return_value = _FakeBatchEncoding(
        {
            "input_ids": input_ids,
            "attention_mask": torch.tensor([[1, 1, 1]]),
        }
    )
    tokenizer.decode.return_value = "Lonjakan harga beras premium Q2"

    return model, tokenizer


def test_generate_label_returns_string():
    model, tokenizer = _mock_model_and_tokenizers()

    with patch("labeling.llm.get_model_and_tokenizer", return_value=(model, tokenizer)):
        label = generate_label(
            [
                {"title": "Harga beras naik", "first_paragraph": "Melonjak tajam."},
            ]
        )

    assert isinstance(label, str)
    assert len(label) > 0
    assert label == "Lonjakan harga beras premium Q2"


def test_generate_label_truncates_long_output():
    model, tokenizer = _mock_model_and_tokenizers()
    tokenizer.decode.return_value = "x" * 300

    with patch("labeling.llm.get_model_and_tokenizer", return_value=(model, tokenizer)):
        label = generate_label(
            [
                {"title": "Test", "first_paragraph": "Test"},
            ]
        )

    assert len(label) <= 200
    assert label.endswith("...")


def test_singleton_loaded_once():
    import labeling.llm as mod

    original_model = mod._model
    original_tokenizer = mod._tokenizer

    try:
        mod._model = None
        mod._tokenizer = None

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()

        with patch(
            "labeling.llm._load_model_and_tokenizer", return_value=(mock_model, mock_tokenizer)
        ):
            m1, t1 = get_model_and_tokenizer()
            m2, t2 = get_model_and_tokenizer()

        assert m1 is m2
        assert t1 is t2
    finally:
        mod._model = original_model
        mod._tokenizer = original_tokenizer
