from unittest.mock import MagicMock, patch

from labeling.llm import deduplicate_claims, extract_article_claims, generate_label, get_llm


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


def _make_mock_llm(content: str) -> MagicMock:
    llm = MagicMock()
    llm.create_chat_completion.return_value = {"choices": [{"message": {"content": content}}]}
    return llm


# ── extract_article_claims ──────────────────────────────────────────────────

def test_extract_article_claims_parses_entity_and_claims():
    raw = "ENTITAS: Pemerintah Indonesia\nKLAIM: Harga BBM naik 30%\nKLAIM: Efektif mulai September"
    with patch("labeling.llm.get_llm", return_value=_make_mock_llm(raw)):
        result = extract_article_claims("BBM Naik", "Isi artikel.")
    assert result["main_entity"] == "Pemerintah Indonesia"
    assert result["information_claims"] == ["Harga BBM naik 30%", "Efektif mulai September"]


def test_extract_article_claims_tolerates_missing_entity():
    raw = "KLAIM: Satu klaim saja"
    with patch("labeling.llm.get_llm", return_value=_make_mock_llm(raw)):
        result = extract_article_claims("Judul", "Isi.")
    assert result["main_entity"] is None
    assert result["information_claims"] == ["Satu klaim saja"]


def test_extract_article_claims_empty_response():
    with patch("labeling.llm.get_llm", return_value=_make_mock_llm("")):
        result = extract_article_claims("Judul", "Isi.")
    assert result["main_entity"] is None
    assert result["information_claims"] == []


def test_extract_article_claims_case_insensitive_prefix():
    raw = "entitas: BI\nklaim: Suku bunga turun"
    with patch("labeling.llm.get_llm", return_value=_make_mock_llm(raw)):
        result = extract_article_claims("Judul", "Isi.")
    assert result["main_entity"] == "BI"
    assert result["information_claims"] == ["Suku bunga turun"]


# ── deduplicate_claims ──────────────────────────────────────────────────────

def test_deduplicate_claims_parses_output():
    raw = "KLAIM: Fakta unik A\nKLAIM: Fakta unik B"
    with patch("labeling.llm.get_llm", return_value=_make_mock_llm(raw)):
        result = deduplicate_claims([["Fakta unik A", "Fakta duplikat"], ["Fakta unik B"]])
    assert result == ["Fakta unik A", "Fakta unik B"]


def test_deduplicate_claims_empty_input_skips_llm():
    with patch("labeling.llm.get_llm") as mock_get:
        result = deduplicate_claims([])
    mock_get.assert_not_called()
    assert result == []


def test_deduplicate_claims_empty_response():
    with patch("labeling.llm.get_llm", return_value=_make_mock_llm("Tidak ada klaim yang unik.")):
        result = deduplicate_claims([["A", "B"]])
    assert result == []
