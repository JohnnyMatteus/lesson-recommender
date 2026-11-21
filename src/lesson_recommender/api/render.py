"""Monta a resposta de recomendações e registra métricas; compartilhado pelas rotas."""

from __future__ import annotations

import logging

from opentelemetry import trace

from lesson_recommender.api.schemas import RecommendationOut, RecommendationsResponse
from lesson_recommender.observability import EMPTY_RECOMMENDATIONS, RECOMMENDATIONS
from lesson_recommender.recommender.hybrid import HybridRecommender, Recommendation

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def _dominant_signal(item: Recommendation, recommender: HybridRecommender) -> str:
    w = recommender.weights
    contributions = {
        "content": w.content * item.breakdown.content,
        "collaborative": w.collaborative * item.breakdown.collaborative,
        "popularity": w.popularity * item.breakdown.popularity,
    }
    return max(contributions, key=lambda key: contributions[key])


def build_response(
    recommender: HybridRecommender, student_id: str, k: int
) -> RecommendationsResponse:
    with tracer.start_as_current_span("recommend") as span:
        span.set_attribute("student.id", student_id)
        span.set_attribute("recommendation.k", k)
        items = recommender.recommend(student_id, k)
        span.set_attribute("recommendation.count", len(items))
    if not items:
        EMPTY_RECOMMENDATIONS.inc()
    for item in items:
        RECOMMENDATIONS.labels(_dominant_signal(item, recommender)).inc()
    logger.info(
        "recomendações geradas",
        extra={"student_id": student_id, "k": k, "returned": len(items)},
    )
    w = recommender.weights
    return RecommendationsResponse(
        student_id=student_id,
        k=k,
        weights={
            "content": w.content,
            "collaborative": w.collaborative,
            "popularity": w.popularity,
        },
        items=[RecommendationOut.from_domain(item) for item in items],
    )
