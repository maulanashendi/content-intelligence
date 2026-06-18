from analyst.schemas import ArticleFeatures, UserNeedScore

TEMPO_REFERENCE_VECTORS = {
    "Update me":           [1, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0],
    "Keep me engaged":     [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    "Educate me":          [0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    "Give me perspective": [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    "Inspire me":          [0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    "Divert me":           [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Help me":             [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    "Connect me":          [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0]
}

LOGIC_RULES = {
    "Update me": {
        "must_have_all": [],
        "must_have_one_of": ["f01_breaking", "f10_conflict_tragedy", "f05_data_investigative"],
        "reject_if_any": ["f03_timeless", "f12_actionable_steps", "f06_author_voice"],
        "boosters": ["f08_expert_quotes", "f07_depth_analysis"]
    },

    "Keep me engaged": {
        "must_have_all": [],
        "must_have_one_of": ["f16_social_buzz", "f02_live_developing"],
        "reject_if_any": ["f04_explanatory"],
        "boosters": ["f01_breaking"]
    },

    "Educate me": {
        "must_have_all": [],
        "must_have_one_of": ["f03_timeless", "f04_explanatory"],
        "reject_if_any": ["f06_author_voice"],

        "boosters": ["f05_data_investigative", "f08_expert_quotes"]
    },

    "Give me perspective": {
        "must_have_all": [],
        "must_have_one_of": ["f07_depth_analysis", "f06_author_voice"],
        "reject_if_any": ["f12_actionable_steps", "f01_breaking", "f04_explanatory"],

        "boosters": ["f08_expert_quotes"]
    },

    "Inspire me": {
        "must_have_all": ["f09_emotional_positive"],
        "must_have_one_of": [],
        "reject_if_any": ["f10_conflict_tragedy", "f01_breaking"],
        "boosters": ["f03_timeless"]
    },

    "Divert me": {
        "must_have_all": [],
        "must_have_one_of": ["f11_light_humor", "f15_listicle_format"],
        "reject_if_any": ["f10_conflict_tragedy"],
        "boosters": ["f16_social_buzz"]
    },

    "Help me": {
        "must_have_all": ["f12_actionable_steps"],
        "must_have_one_of": [],
        "reject_if_any": ["f13_collective_call"],
        "boosters": ["f03_timeless"]
    },

    "Connect me": {
        "must_have_all": ["f13_collective_call"],
        "must_have_one_of": [],
        "reject_if_any": ["f12_actionable_steps", "f01_breaking"],
        "boosters": ["f10_conflict_tragedy", "f14_community_identity"]
    }
}


def rank_user_needs(features: ArticleFeatures) -> list[UserNeedScore]:
    features_full = features.model_dump()
    features_dict = {key: val["status"] for key, val in features_full.items()}
    vector = list(features_dict.values())

    scores: list[UserNeedScore] = []
    for category, rules in LOGIC_RULES.items():
        ref_vector = TEMPO_REFERENCE_VECTORS[category]
        matches = sum(1 for a, b in zip(vector, ref_vector, strict=False) if a == b)
        base_score = (matches / 16) * 100

        rejected = False
        for f_key in rules["reject_if_any"]:
            if features_dict.get(f_key) == 1:
                base_score = 0.0
                rejected = True
                break
        if rejected:
            scores.append(UserNeedScore(category=category, score=0.0))
            continue

        if rules["must_have_all"] and any(
            features_dict.get(f_key) == 0 for f_key in rules["must_have_all"]
        ):
            base_score *= 0.3

        if rules["must_have_one_of"] and not any(
            features_dict.get(f_key) == 1 for f_key in rules["must_have_one_of"]
        ):
            base_score *= 0.5

        for f_key in rules["boosters"]:
            if features_dict.get(f_key) == 1:
                base_score += 5

        scores.append(UserNeedScore(category=category, score=min(base_score, 100.0)))

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores
