"""Decorator de cache sobre qualquer `Recommender`."""

from __future__ import annotations

from lesson_recommender.recommender.hybrid import Recommendation, Weights
from lesson_recommender.recommender.ports import RecommendationCache, Recommender


class CachedRecommender:
    """Mesma interface do recomendador decorado; consulta o cache antes de ranquear.

    Erros de validação (k fora do intervalo, aluno inexistente) vêm do recomendador decorado e
    nunca são guardados: só respostas válidas entram no cache.
    """

    def __init__(self, inner: Recommender, cache: RecommendationCache) -> None:
        self._inner = inner
        self._cache = cache

    @property
    def weights(self) -> Weights:
        return self._inner.weights

    def recommend(self, student_id: str, k: int) -> list[Recommendation]:
        cached = self._cache.get(student_id, k)
        if cached is not None:
            return cached
        items = self._inner.recommend(student_id, k)
        self._cache.put(student_id, k, items)
        return items
