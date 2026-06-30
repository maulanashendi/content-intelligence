from core.taxonomy import USER_NEED_CATEGORIES
from labeling.pipeline import aggregate_user_needs


def test_empty_or_none_returns_nulls() -> None:
    assert aggregate_user_needs(None) == (None, None, 0)
    assert aggregate_user_needs([]) == (None, None, 0)
    assert aggregate_user_needs([[], []]) == (None, None, 0)


def test_counts_frequency_over_eight_keys() -> None:
    dist, dominant, reps = aggregate_user_needs(
        [["Update me", "Give me perspective"], ["Update me"], ["Educate me"]]
    )
    assert set(dist) == set(USER_NEED_CATEGORIES)
    assert dist["Update me"] == 2
    assert dist["Give me perspective"] == 1
    assert dist["Educate me"] == 1
    assert dist["Divert me"] == 0
    assert dominant == "Update me"
    assert reps == 3


def test_normalizes_and_drops_unknown() -> None:
    dist, dominant, reps = aggregate_user_needs([["update me", "Garbage need"], ["???"]])
    assert dist["Update me"] == 1   # casefold-normalized
    assert dominant == "Update me"
    assert reps == 1                # second article contributed nothing


def test_dedupes_and_caps_at_two_per_article() -> None:
    dist, _, reps = aggregate_user_needs([["Update me", "Update me", "Educate me", "Divert me"]])
    assert dist["Update me"] == 1        # de-duped within the article
    assert dist["Educate me"] == 1
    assert dist["Divert me"] == 0        # capped at 2 distinct needs
    assert reps == 1


def test_dominant_tie_break_follows_taxonomy_order() -> None:
    # "Update me" and "Educate me" both count 1; "Update me" precedes in USER_NEED_CATEGORIES.
    _, dominant, _ = aggregate_user_needs([["Educate me"], ["Update me"]])
    assert dominant == "Update me"
