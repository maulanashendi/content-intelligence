from unittest.mock import MagicMock, patch

import pytest
from core.config import settings
from labeling.llm import (
    _parse_cluster_insight,
    generate_label,
    get_llm,
)
from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM


def _make_mock_llm(content: str) -> MagicMock:
    llm = MagicMock()
    llm.create_chat_completion.return_value = {"choices": [{"message": {"content": content}}]}
    llm.tokenize.return_value = [0] * 100  # short token count so budget guard never trims
    return llm


# ── generate_label ──────────────────────────────────────────────────────────

async def test_generate_label_returns_string(monkeypatch):
    monkeypatch.setattr(settings, "labeling_provider", "local")
    llm = _make_mock_llm("Lonjakan harga beras premium")
    with patch("labeling.llm.get_llm", return_value=llm):
        label = await generate_label([{"title": "Harga beras naik", "first_paragraph": "Melonjak tajam."}])
    assert isinstance(label, str)
    assert label == "Lonjakan harga beras premium"


async def test_generate_label_strips_punctuation_and_newlines(monkeypatch):
    monkeypatch.setattr(settings, "labeling_provider", "local")
    llm = _make_mock_llm("Harga beras premium terus naik.\nPenjelasan tambahan")
    with patch("labeling.llm.get_llm", return_value=llm):
        label = await generate_label([{"title": "Test", "first_paragraph": "Test"}])
    assert label == "Harga beras premium terus naik"


def test_singleton_loaded_once():
    import labeling.llm as mod

    original_llm = mod._llm
    try:
        mod._llm = None
        mock_llama_class = MagicMock()
        mock_instance = MagicMock()
        mock_llama_class.return_value = mock_instance

        with (
            patch("labeling.llm._load_llama_class", return_value=mock_llama_class),
            patch("labeling.llm._resolve_model_path", return_value="/fake/model.gguf"),
        ):
            llm1 = get_llm()
            llm2 = get_llm()

        assert llm1 is llm2
        mock_llama_class.assert_called_once()
    finally:
        mod._llm = original_llm


# ── _parse_cluster_insight ──────────────────────────────────────────────────

def test_parse_cluster_insight_canonical():
    raw = (
        "LABEL: Kenaikan Harga Beras Nasional\n"
        "APA_TERJADI: Harga beras naik 30% bulan ini.\n"
        "SUDUT: Dampak pada ketahanan pangan perlu segera diliput.\n"
        "PIHAK: Kementerian Perdagangan\n"
        "PIHAK: Bulog\n"
        "KLAIM: Harga beras premium melonjak 30%\n"
        "KLAIM: Pemerintah berencana impor"
    )
    result = _parse_cluster_insight(raw)
    assert result["label"] == "Kenaikan Harga Beras Nasional"
    assert result["what_happened"] == "Harga beras naik 30% bulan ini."
    assert result["editorial_angle"] == "Dampak pada ketahanan pangan perlu segera diliput."
    assert result["parties_involved"] == ["Kementerian Perdagangan", "Bulog"]
    assert result["summary"] == ["Harga beras premium melonjak 30%", "Pemerintah berencana impor"]


def test_parse_cluster_insight_tolerates_markdown_bold():
    raw = (
        "**LABEL:** Topik beras naik\n"
        "**SUDUT:** Angle penting\n"
    )
    result = _parse_cluster_insight(raw)
    assert result["label"] == "Topik beras naik"
    assert result["editorial_angle"] == "Angle penting"


def test_parse_cluster_insight_tolerates_numbered_lines():
    raw = (
        "1. LABEL: Topik bernomor\n"
        "2. SUDUT: Angle bernomor\n"
        "3. KLAIM: Fakta bernomor\n"
    )
    result = _parse_cluster_insight(raw)
    assert result["label"] == "Topik bernomor"
    assert result["editorial_angle"] == "Angle bernomor"
    assert result["summary"] == ["Fakta bernomor"]


def test_parse_cluster_insight_tolerates_space_before_colon():
    raw = "SUDUT : Angle dengan spasi sebelum titik dua"
    result = _parse_cluster_insight(raw)
    assert result["editorial_angle"] == "Angle dengan spasi sebelum titik dua"


def test_parse_cluster_insight_tolerates_apa_terjadi_with_space():
    raw = "APA TERJADI: Terjadi sesuatu penting"
    result = _parse_cluster_insight(raw)
    assert result["what_happened"] == "Terjadi sesuatu penting"


def test_parse_cluster_insight_ignores_pihak_none_markers():
    raw = "LABEL: Topik\nPIHAK: tidak disebutkan\nPIHAK: Badan Valid"
    result = _parse_cluster_insight(raw)
    assert result["parties_involved"] == ["Badan Valid"]


def test_parse_cluster_insight_zero_fields_returns_all_none():
    result = _parse_cluster_insight("Ini bukan format yang benar sama sekali.")
    assert result["label"] is None
    assert result["what_happened"] is None
    assert result["parties_involved"] is None
    assert result["editorial_angle"] is None
    assert result["summary"] is None


def test_parse_cluster_insight_case_insensitive():
    raw = "label: Topik kecil\nsudut: Angle kecil"
    result = _parse_cluster_insight(raw)
    assert result["label"] == "Topik kecil"
    assert result["editorial_angle"] == "Angle kecil"


# ── generate_cluster_insight (budget trim + zero-field warning) ─────────────

@pytest.mark.asyncio
async def test_generate_cluster_insight_warns_on_zero_fields(caplog, monkeypatch):
    import logging
    monkeypatch.setattr(settings, "labeling_provider", "local")
    llm = MagicMock()
    llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "Tidak ada format yang cocok sama sekali."}}]
    }
    # High token count ensures trim loop exits immediately (budget always satisfied)
    llm.tokenize.return_value = [0] * 100

    from labeling.llm import generate_cluster_insight

    with (
        patch("labeling.llm.get_llm", return_value=llm),
        caplog.at_level(logging.WARNING, logger="labeling.llm"),
    ):
        result = await generate_cluster_insight([{"title": "T", "first_paragraph": "P"}])

    assert result["label"] is None
    assert result["editorial_angle"] is None
    assert any("zero fields" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_generate_cluster_insight_trims_reps_when_budget_exceeded(caplog, monkeypatch):
    import logging
    monkeypatch.setattr(settings, "labeling_provider", "local")

    call_count = 0

    def fake_tokenize(text: bytes) -> list:
        nonlocal call_count
        call_count += 1
        # First call: over budget (4096 tokens); subsequent: under budget
        if call_count == 1:
            return [0] * 4000
        return [0] * 100

    llm = MagicMock()
    llm.tokenize.side_effect = fake_tokenize
    llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "LABEL: Topik Valid\nSUDUT: Angle valid"}}]
    }

    from labeling.llm import generate_cluster_insight

    reps = [
        {"title": f"Artikel {i}", "first_paragraph": f"Para {i}"}
        for i in range(5)
    ]
    with (
        patch("labeling.llm.get_llm", return_value=llm),
        caplog.at_level(logging.WARNING, logger="labeling.llm"),
    ):
        result = await generate_cluster_insight(reps)

    assert result["label"] == "Topik Valid"
    assert any("trimmed" in r.message for r in caplog.records)


# ── provider dispatcher ─────────────────────────────────────────────────────


async def test_cluster_insight_routes_to_api(monkeypatch) -> None:
    monkeypatch.setattr(settings, "labeling_provider", "openrouter")
    import labeling.llm as lm
    monkeypatch.setattr(lm, "build_client", lambda *a, **k: "CLIENT")
    captured = {}

    async def fake_cs(client, model, messages, schema):
        captured["client"] = client
        captured["model"] = model
        captured["schema"] = schema
        return ClusterInsightLLM(label="Topik uji", parties_involved=["A"])

    monkeypatch.setattr(lm, "complete_structured", fake_cs)
    out = await lm.generate_cluster_insight([{"title": "t", "first_paragraph": "p"}])
    assert out["label"] == "Topik uji"
    assert out["parties_involved"] == ["A"]
    assert set(out) == {"label", "what_happened", "parties_involved", "editorial_angle", "summary", "desk_category", "user_need_category"}
    assert captured["client"] == "CLIENT"
    assert captured["model"] == settings.labeling_model
    assert captured["schema"] is ClusterInsightLLM


async def test_label_routes_to_api(monkeypatch) -> None:
    monkeypatch.setattr(settings, "labeling_provider", "openrouter")
    import labeling.llm as lm
    monkeypatch.setattr(lm, "build_client", lambda *a, **k: "CLIENT")

    async def fake_cs(client, model, messages, schema):
        return ClusterLabelLLM(label="  Label Uji  ")

    monkeypatch.setattr(lm, "complete_structured", fake_cs)
    out = await lm.generate_label([{"title": "t", "first_paragraph": "p"}])
    assert out == "Label Uji"


async def test_label_api_provider_resolves_api_to_openrouter(monkeypatch) -> None:
    # "api" is the documented LABELING_PROVIDER switch; build_client only accepts preset names
    # so "api" must be resolved to the openrouter preset before being forwarded.
    monkeypatch.setattr(settings, "labeling_provider", "api")
    import labeling.llm as lm

    captured: dict = {}
    monkeypatch.setattr(lm, "build_client", lambda provider, *a, **k: captured.__setitem__("provider", provider) or "CLIENT")

    async def fake_cs(client, model, messages, schema):
        return ClusterLabelLLM(label="X")

    monkeypatch.setattr(lm, "complete_structured", fake_cs)
    await lm.generate_label([{"title": "t", "first_paragraph": "p"}])
    assert captured["provider"] == "openrouter"


async def test_cluster_insight_local_uses_gemma(monkeypatch) -> None:
    monkeypatch.setattr(settings, "labeling_provider", "local")
    import labeling.llm as lm
    called = {"build": False}
    monkeypatch.setattr(lm, "build_client", lambda *a, **k: called.__setitem__("build", True))
    llm = _make_mock_llm("LABEL: Topik lokal\nAPA_TERJADI: Sesuatu terjadi")
    monkeypatch.setattr(lm, "get_llm", lambda: llm)
    out = await lm.generate_cluster_insight([{"title": "t", "first_paragraph": "p"}])
    assert out["label"] == "Topik lokal"
    assert called["build"] is False  # API client never built on the local path


def test_parse_cluster_insight_extracts_desk_and_user_need() -> None:
    from labeling.llm import _parse_cluster_insight

    raw = (
        "LABEL: Sidang korupsi pejabat daerah\n"
        "APA_TERJADI: Terdakwa hadir di pengadilan.\n"
        "SUDUT: Telusuri aliran dana.\n"
        "PIHAK: KPK\n"
        "KLAIM: Dana mengalir ke proyek fiktif.\n"
        "DESK: Hukum\n"
        "KEBUTUHAN: Update me\n"
    )
    result = _parse_cluster_insight(raw)
    assert result["desk_category"] == "Hukum"
    assert result["user_need_category"] == "Update me"


def test_parse_cluster_insight_missing_classification_is_none() -> None:
    from labeling.llm import _parse_cluster_insight

    raw = "LABEL: Topik tanpa klasifikasi\n"
    result = _parse_cluster_insight(raw)
    assert result["desk_category"] is None
    assert result["user_need_category"] is None
