"""Portas do caso de uso de recomendação: quem recomenda e onde o resultado fica em cache."""

from __future__ import annotations

from typing import Protocol

from lesson_recommender.recommender.hybrid import Recommendation, Weights


class Recommender(Protocol):
    @property
    def weights(self) -> Weights: ...

    def recommend(self, student_id: str, k: int) -> list[Recommendation]: ...


class RecommendationCache(Protocol):
    """Cache das recomendações por aluno. Falhas do cache nunca derrubam a recomendação."""

    def get(self, student_id: str, k: int) -> list[Recommendation] | None: ...

    def put(self, student_id: str, k: int, items: list[Recommendation]) -> None: ...

    def invalidate(self, student_id: str) -> None: ...
