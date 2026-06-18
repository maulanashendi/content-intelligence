from analyst.category import rank_user_needs
from analyst.schemas import ArticleFeatures

_NAMES = [
    "f01_breaking", "f02_live_developing", "f03_timeless", "f04_explanatory",
    "f05_data_investigative", "f06_author_voice", "f07_depth_analysis",
    "f08_expert_quotes", "f09_emotional_positive", "f10_conflict_tragedy",
    "f11_light_humor", "f12_actionable_steps", "f13_collective_call",
    "f14_community_identity", "f15_listicle_format", "f16_social_buzz",
]


def _features(active: set[str]) -> ArticleFeatures:
    return ArticleFeatures.model_validate(
        {n: {"status": 1 if n in active else 0, "reasoning": ""} for n in _NAMES}
    )


def test_actionable_howto_ranks_help_me_top() -> None:
    # f12_actionable_steps + f03_timeless → "Help me" must_have_all satisfied + booster
    ranked = rank_user_needs(_features({"f12_actionable_steps", "f03_timeless"}))
    assert ranked[0].category == "Help me"
    assert ranked[0].score > ranked[1].score


def test_returns_all_eight_categories_sorted() -> None:
    ranked = rank_user_needs(_features(set()))
    assert len(ranked) == 8
    assert ranked == sorted(ranked, key=lambda s: s.score, reverse=True)


def test_reject_rule_zeroes_score() -> None:
    # "Help me" rejects if f13_collective_call is set
    ranked = rank_user_needs(_features({"f12_actionable_steps", "f13_collective_call"}))
    help_me = next(s for s in ranked if s.category == "Help me")
    assert help_me.score == 0.0
