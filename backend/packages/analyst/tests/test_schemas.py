from analyst.schemas import (
    AnalyzeResult,
    ArticleAnalysisResult,
    RecommendationOutput,
    UserNeedScore,
)


def _feature(status: int) -> dict:
    return {"status": status, "reasoning": "x"}


def _all_features(status: int = 0) -> dict:
    return {f"f{n:02d}_x": _feature(status) for n in range(1, 17)}


def test_analysis_result_parses_16_features() -> None:
    payload = {
        "features": {
            k: v
            for k, v in zip(
                [
                    "f01_breaking", "f02_live_developing", "f03_timeless",
                    "f04_explanatory", "f05_data_investigative", "f06_author_voice",
                    "f07_depth_analysis", "f08_expert_quotes", "f09_emotional_positive",
                    "f10_conflict_tragedy", "f11_light_humor", "f12_actionable_steps",
                    "f13_collective_call", "f14_community_identity", "f15_listicle_format",
                    "f16_social_buzz",
                ],
                [_feature(0)] * 16,
            )
        },
        "feedback": {
            "recommendation_judul": ["a"],
            "missing_info": [],
            "bias_check": [],
            "next_angle": [],
        },
    }
    result = ArticleAnalysisResult.model_validate(payload)
    assert result.features.f01_breaking.status == 0


def test_analyze_result_round_trip() -> None:
    res = AnalyzeResult(
        features=ArticleAnalysisResult.model_validate(
            {
                "features": {
                    name: _feature(0)
                    for name in [
                        "f01_breaking", "f02_live_developing", "f03_timeless",
                        "f04_explanatory", "f05_data_investigative", "f06_author_voice",
                        "f07_depth_analysis", "f08_expert_quotes", "f09_emotional_positive",
                        "f10_conflict_tragedy", "f11_light_humor", "f12_actionable_steps",
                        "f13_collective_call", "f14_community_identity", "f15_listicle_format",
                        "f16_social_buzz",
                    ]
                },
                "feedback": {
                    "recommendation_judul": [], "missing_info": [],
                    "bias_check": [], "next_angle": [],
                },
            }
        ).features,
        editorial_feedback=ArticleAnalysisResult.model_validate(
            {
                "features": {
                    name: _feature(0)
                    for name in [
                        "f01_breaking", "f02_live_developing", "f03_timeless",
                        "f04_explanatory", "f05_data_investigative", "f06_author_voice",
                        "f07_depth_analysis", "f08_expert_quotes", "f09_emotional_positive",
                        "f10_conflict_tragedy", "f11_light_humor", "f12_actionable_steps",
                        "f13_collective_call", "f14_community_identity", "f15_listicle_format",
                        "f16_social_buzz",
                    ]
                },
                "feedback": {
                    "recommendation_judul": [], "missing_info": [],
                    "bias_check": [], "next_angle": [],
                },
            }
        ).feedback,
        user_needs=[UserNeedScore(category="Help me", score=100.0)],
    )
    assert res.user_needs[0].category == "Help me"


def test_recommendation_output_defaults() -> None:
    out = RecommendationOutput(filters_applied={}, summary="s")
    assert out.data_source == "mock"
    assert out.insights == []
