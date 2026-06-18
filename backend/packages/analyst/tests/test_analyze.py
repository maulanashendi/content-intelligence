import pytest
from analyst import analyze
from analyst.schemas import ArticleAnalysisResult, ArticleRequest

_NAMES = [
    "f01_breaking", "f02_live_developing", "f03_timeless", "f04_explanatory",
    "f05_data_investigative", "f06_author_voice", "f07_depth_analysis",
    "f08_expert_quotes", "f09_emotional_positive", "f10_conflict_tragedy",
    "f11_light_humor", "f12_actionable_steps", "f13_collective_call",
    "f14_community_identity", "f15_listicle_format", "f16_social_buzz",
]


def _canned(active: set[str]) -> ArticleAnalysisResult:
    return ArticleAnalysisResult.model_validate(
        {
            "features": {
                n: {"status": 1 if n in active else 0, "reasoning": ""} for n in _NAMES
            },
            "feedback": {
                "recommendation_judul": ["Judul"], "missing_info": [],
                "bias_check": [], "next_angle": [],
            },
        }
    )


@pytest.fixture
def patched_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(task: str, messages: list[dict], schema: type) -> ArticleAnalysisResult:
        assert task == "analyze"
        return _canned({"f12_actionable_steps", "f03_timeless"})

    monkeypatch.setattr(analyze.llm, "complete_for_task", fake)


async def test_run_analysis_returns_two_user_needs(patched_llm: None) -> None:
    result = await analyze.run_analysis("t", "c")
    assert len(result.user_needs) == 2
    assert result.user_needs[0].category == "Help me"
    assert result.editorial_feedback.recommendation_judul == ["Judul"]


async def test_batch_runs_all(patched_llm: None) -> None:
    results = await analyze.run_analysis_batch(
        [ArticleRequest(title="t", content="c"), ArticleRequest(title="t2", content="c2")]
    )
    assert len(results) == 2
    assert all(r.user_needs[0].category == "Help me" for r in results)
