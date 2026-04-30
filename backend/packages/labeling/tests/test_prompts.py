import labeling.prompts as prompts


def test_format_messages_basic():
    articles = [
        {"title": "Harga beras naik", "first_paragraph": "Harga beras premium melonjak."},
        {"title": "Gandum impor turun", "first_paragraph": None},
    ]
    messages = prompts.format_messages(articles)

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "Harga beras naik" in content
    assert "Gandum impor turun" in content
    assert "2" in content


def test_format_messages_empty_first_paragraph():
    articles = [
        {"title": "Test title", "first_paragraph": None},
    ]
    messages = prompts.format_messages(articles)
    content = messages[0]["content"]
    assert "Test title" in content


def test_system_prompt_is_string():
    assert isinstance(prompts.SYSTEM_PROMPT, str)
    assert len(prompts.SYSTEM_PROMPT) > 0
