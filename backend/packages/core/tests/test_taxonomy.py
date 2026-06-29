from core.taxonomy import (
    DESK_CATEGORIES,
    USER_NEED_CATEGORIES,
    normalize_desk,
    normalize_user_need,
)


def test_desk_categories_include_allowed_and_rejected():
    assert "Politik" in DESK_CATEGORIES
    assert "Hiburan" in DESK_CATEGORIES
    assert "Lainnya" in DESK_CATEGORIES


def test_user_need_categories_has_eight():
    assert len(USER_NEED_CATEGORIES) == 8
    assert "Update me" in USER_NEED_CATEGORIES
    assert "Divert me" in USER_NEED_CATEGORIES


def test_normalize_desk_canonicalizes_case_and_whitespace():
    assert normalize_desk("  politik ") == "Politik"
    assert normalize_desk("EKONOMI & BISNIS") == "Ekonomi & Bisnis"


def test_normalize_desk_rejects_unknown_and_empty():
    assert normalize_desk("Astrologi") is None
    assert normalize_desk("") is None
    assert normalize_desk(None) is None


def test_normalize_user_need_canonicalizes_and_rejects():
    assert normalize_user_need("update me") == "Update me"
    assert normalize_user_need("Bikin Senang") is None
    assert normalize_user_need(None) is None
