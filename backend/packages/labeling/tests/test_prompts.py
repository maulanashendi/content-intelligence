import labeling.prompts as prompts


def test_format_messages_basic():
    articles = [
        {"title": "Harga beras naik", "first_paragraph": "Harga beras premium melonjak."},
        {"title": "Gandum impor turun", "first_paragraph": None},
    ]
    messages = prompts.format_messages(articles)

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert prompts.SYSTEM_PROMPT in messages[0]["content"]
    assert "Harga beras naik" in messages[0]["content"]
    assert "Gandum impor turun" in messages[0]["content"]
    assert "2 artikel" in messages[0]["content"]


def test_format_messages_empty_first_paragraph():
    articles = [
        {"title": "Test title", "first_paragraph": None},
    ]
    messages = prompts.format_messages(articles)
    assert "Test title" in messages[0]["content"]
    assert "Paragraf awal: -" in messages[0]["content"]


def test_system_prompt_is_string():
    assert isinstance(prompts.SYSTEM_PROMPT, str)
    assert len(prompts.SYSTEM_PROMPT) > 0


# ── extract prompt ──────────────────────────────────────────────────────────

def test_format_extract_messages_contains_title_and_content():
    msgs = prompts.format_extract_messages("Harga BBM Naik", "Pemerintah menaikkan harga BBM.")
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "Harga BBM Naik" in msgs[0]["content"]
    assert "Pemerintah menaikkan harga BBM." in msgs[0]["content"]
    assert "ENTITAS" in msgs[0]["content"]
    assert "KLAIM" in msgs[0]["content"]


def test_format_extract_messages_truncates_long_content():
    long_content = "x" * 5000
    msgs = prompts.format_extract_messages("T", long_content)
    assert len(msgs[0]["content"]) < 5000 + 200  # well under original + prompt overhead
    assert "x" * prompts._CONTENT_MAX_CHARS in msgs[0]["content"]
    assert "x" * (prompts._CONTENT_MAX_CHARS + 1) not in msgs[0]["content"]


# ── dedup prompt ────────────────────────────────────────────────────────────

def test_format_dedup_messages_includes_all_claims():
    all_claims = [["Klaim A", "Klaim B"], ["Klaim C"]]
    msgs = prompts.format_dedup_messages(all_claims)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "Klaim A" in msgs[0]["content"]
    assert "Klaim B" in msgs[0]["content"]
    assert "Klaim C" in msgs[0]["content"]


def test_format_dedup_messages_caps_at_max_claims():
    # 70 claims exceeds the cap of 60
    all_claims = [[f"Klaim {i}" for i in range(70)]]
    msgs = prompts.format_dedup_messages(all_claims)
    assert "Klaim 59" in msgs[0]["content"]
    assert "Klaim 60" not in msgs[0]["content"]


def test_format_dedup_messages_empty_input():
    msgs = prompts.format_dedup_messages([])
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
