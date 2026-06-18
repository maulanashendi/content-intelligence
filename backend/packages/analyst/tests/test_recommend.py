import pytest
from analyst import recommend
from analyst.schemas import (
    DataFilterParameters,
    RecommendationInsight,
    RecommendationInsightsLLM,
    RecommendationRequest,
)

_ROWS = [
    {"rubrics_sb": "Politik", "total_views": 5000, "user_need_model": "Update me"},
    {"rubrics_sb": "Olahraga", "total_views": 100, "user_need_model": "Divert me"},
    {"rubrics_sb": "Politik", "total_views": 50, "user_need_model": "Educate me"},
]


def test_apply_filters_category_and_minviews() -> None:
    filtered = recommend._apply_filters(
        _ROWS, DataFilterParameters(category="politik", min_page_views=1000)
    )
    assert len(filtered) == 1
    assert filtered[0]["total_views"] == 5000


def test_apply_filters_sorts_by_views_desc() -> None:
    filtered = recommend._apply_filters(_ROWS, DataFilterParameters())
    views = [r["total_views"] for r in filtered]
    assert views == sorted(views, reverse=True)


async def test_run_recommendation_two_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommend, "_load_data", lambda: _ROWS)

    async def fake(task: str, messages: list[dict], schema: type):
        assert task == "recommend"
        if schema is DataFilterParameters:
            return DataFilterParameters(category="Politik", min_page_views=1000)
        return RecommendationInsightsLLM(
            insights=[RecommendationInsight(title="t", insight="i", action="a")],
            summary="ringkasan",
        )

    monkeypatch.setattr(recommend.llm, "complete_for_task", fake)

    out = await recommend.run_recommendation(RecommendationRequest(intent="politik viral"))
    assert out.summary == "ringkasan"
    assert out.data_source == "airflow_json"
    assert out.filters_applied == {"category": "Politik", "min_page_views": 1000}
    assert len(out.insights) == 1
