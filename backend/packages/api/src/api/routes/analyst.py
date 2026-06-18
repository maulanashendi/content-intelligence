import logging

from analyst import analyze, recommend
from analyst.schemas import (
    AnalyzeResult,
    ArticleRequest,
    BatchArticleRequest,
    RecommendationOutput,
    RecommendationRequest,
)
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.post("/analyze", response_model=AnalyzeResult, status_code=200, summary="Score one article on 16 editorial features + user needs")
async def analyze_article(body: ArticleRequest) -> AnalyzeResult:
    try:
        return await analyze.run_analysis(body.title, body.content)
    except Exception as exc:
        logger.error("analyst analyze failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Analysis failed") from exc


@router.post("/analyze/batch", response_model=list[AnalyzeResult], status_code=200, summary="Score a batch of articles")
async def analyze_batch(body: BatchArticleRequest) -> list[AnalyzeResult]:
    try:
        return await analyze.run_analysis_batch(body.articles)
    except Exception as exc:
        logger.error("analyst batch analyze failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Batch analysis failed") from exc


@router.post("/recommendation", response_model=RecommendationOutput, status_code=200, summary="Editorial recommendation insights from a free-text intent")
async def recommendation(body: RecommendationRequest) -> RecommendationOutput:
    try:
        return await recommend.run_recommendation(body)
    except Exception as exc:
        logger.error("analyst recommendation failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Recommendation failed") from exc
