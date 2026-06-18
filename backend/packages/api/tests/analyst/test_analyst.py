import pytest
from analyst import analyze, recommend
from analyst.schemas import (
    AnalyzeResult,
    ArticleAnalysisResult,
    RecommendationInsight,
    RecommendationOutput,
    UserNeedScore,
)
from api.main import app
from httpx import ASGITransport, AsyncClient

_NAMES = [
    "f01_breaking", "f02_live_developing", "f03_timeless", "f04_explanatory",
    "f05_data_investigative", "f06_author_voice", "f07_depth_analysis",
    "f08_expert_quotes", "f09_emotional_positive", "f10_conflict_tragedy",
    "f11_light_humor", "f12_actionable_steps", "f13_collective_call",
    "f14_community_identity", "f15_listicle_format", "f16_social_buzz",
]


def _analyze_result() -> AnalyzeResult:
    parsed = ArticleAnalysisResult.model_validate(
        {
            "features": {n: {"status": 0, "reasoning": ""} for n in _NAMES},
            "feedback": {
                "recommendation_judul": ["J"], "missing_info": [],
                "bias_check": [], "next_angle": [],
            },
        }
    )
    return AnalyzeResult(
        features=parsed.features,
        editorial_feedback=parsed.feedback,
        user_needs=[UserNeedScore(category="Help me", score=80.0)],
    )


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_analyze_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(title: str, content: str) -> AnalyzeResult:
        return _analyze_result()

    monkeypatch.setattr(analyze, "run_analysis", fake)
    resp = await client.post("/api/v1/analyst/analyze", json={"title": "t", "content": "c"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_needs"][0]["category"] == "Help me"
    assert body["features"]["f01_breaking"]["status"] == 0


async def test_recommendation_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(request) -> RecommendationOutput:
        return RecommendationOutput(
            filters_applied={"category": "Politik"},
            sample_data=[],
            insights=[RecommendationInsight(title="t", insight="i", action="a")],
            summary="s",
            data_source="airflow_json",
        )

    monkeypatch.setattr(recommend, "run_recommendation", fake)
    resp = await client.post("/api/v1/analyst/recommendation", json={"intent": "politik viral"})
    assert resp.status_code == 200
    assert resp.json()["summary"] == "s"


async def test_analyze_failure_maps_to_502(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(title: str, content: str) -> AnalyzeResult:
        raise RuntimeError("llm down")

    monkeypatch.setattr(analyze, "run_analysis", boom)
    resp = await client.post("/api/v1/analyst/analyze", json={"title": "t", "content": "c"})
    assert resp.status_code == 502
