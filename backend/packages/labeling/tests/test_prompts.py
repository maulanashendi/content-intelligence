import labeling.prompts as prompts
from labeling.prompts import format_cluster_insight_messages_api, format_label_messages_api


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


def test_cluster_insight_api_message_has_article_context() -> None:
    msgs = format_cluster_insight_messages_api(
        [{"title": "Harga beras naik", "first_paragraph": "Melonjak tajam di pasar."}]
    )
    assert len(msgs) == 1 and msgs[0]["role"] == "user"
    body = msgs[0]["content"]
    assert "Harga beras naik" in body
    assert "LABEL:" not in body  # JSON schema is injected by complete_structured, not a prefix format


def test_label_api_message_has_article_context() -> None:
    msgs = format_label_messages_api([{"title": "Topik X", "first_paragraph": "Isi."}])
    assert "Topik X" in msgs[0]["content"]
    assert "LABEL:" not in msgs[0]["content"]
