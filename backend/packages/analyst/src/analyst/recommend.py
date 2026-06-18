import json
import logging
from datetime import datetime
from pathlib import Path

from analyst import llm
from analyst.schemas import (
    DataFilterParameters,
    RecommendationInsightsLLM,
    RecommendationOutput,
    RecommendationRequest,
)

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent / "data" / "airflow_data.json"

_SELECTOR_SYSTEM = """You are an editorial data analyst assistant.
Your ONLY job is to extract filter parameters from the user's intent to query our article performance database.

RULES:
- Extract constraints like category, user need, minimum page views, or author.
- If the user doesn't mention a specific constraint, leave it null.
- Your entire response must be valid JSON matching the schema provided.
"""

_INSIGHT_SYSTEM = """You are a senior editorial analytics strategist.
You receive a filtered dataset of article performance and produce structured, actionable insights.

RULES:
- Output using Indonesian language you can use english if needed for specific terms.
- Produce 2 to 4 insights ONLY. No more.
- Each insight must have a concrete editorial action the team can take TODAY.
- The summary must be 2-3 sentences maximum.
- Respond ONLY with valid JSON matching the schema provided.
- Do NOT engage in conversational chat — only analyse the data.
"""


def _load_data() -> list[dict]:
    try:
        return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("analyst recommendation dataset missing", extra={"path": str(_DATA_PATH)})
        return []
    except json.JSONDecodeError:
        logger.error("analyst recommendation dataset is not valid JSON")
        return []


def _apply_filters(data: list[dict], filters: DataFilterParameters) -> list[dict]:
    """Filter the dataset based on the extracted parameters."""
    filtered = []
    for row in data:
        # Filter by category
        if filters.category:
            cat_filter = filters.category.lower()
            rubric = str(row.get("rubrics_sb", "")).lower()
            desk = str(row.get("desk", "")).lower()
            if cat_filter not in rubric and cat_filter not in desk:
                continue

        # Filter by user need
        if filters.user_need_category and filters.user_need_category.lower() != str(row.get("user_need_model", "")).lower():
            continue

        # Filter by minimum page views
        if filters.min_page_views is not None:
            try:
                total_views = int(row.get("total_views") or 0)
            except ValueError:
                total_views = 0
            if total_views < filters.min_page_views:
                continue

        # Filter by author
        if filters.author and "author" in row:
            if filters.author.lower() not in str(row.get("author", "")).lower():
                continue

        # Filter by days_lookback
        if filters.days_lookback:
            try:
                pub_date_str = row.get("publish_date")
                if pub_date_str:
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                    delta = datetime.now() - pub_date
                    if delta.days > filters.days_lookback:
                        continue
            except Exception:
                logger.debug("skipping days_lookback filter for row with unparseable date")

        filtered.append(row)

    # Sort by page views descending by default
    def _get_views(x):
        try:
            return int(x.get("total_views") or 0)
        except ValueError:
            return 0

    filtered.sort(key=_get_views, reverse=True)
    return filtered


async def run_recommendation(request: RecommendationRequest) -> RecommendationOutput:
    filters = await llm.complete_for_task(
        "recommend",
        [
            {"role": "system", "content": _SELECTOR_SYSTEM},
            {"role": "user", "content": f"User intent: {request.intent}"},
        ],
        DataFilterParameters,
    )

    rows = _apply_filters(_load_data(), filters)
    filters_dict = filters.model_dump(exclude_none=True)

    insights = await llm.complete_for_task(
        "recommend",
        [
            {"role": "system", "content": _INSIGHT_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Filters applied:\n{json.dumps(filters_dict, indent=2)}\n\n"
                    f"Data (JSON rows):\n{json.dumps(rows[:20], ensure_ascii=False, indent=2)}\n\n"
                    f"User's original intent: {request.intent}"
                ),
            },
        ],
        RecommendationInsightsLLM,
    )

    return RecommendationOutput(
        filters_applied=filters_dict,
        sample_data=rows[:20],
        insights=insights.insights,
        summary=insights.summary,
        data_source="airflow_json",
    )
