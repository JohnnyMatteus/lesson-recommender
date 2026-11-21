"""Recomendador híbrido: conteúdo + colaborativo + popularidade, depois de filtrar por regras."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lesson_recommender.domain.errors import InvalidRequestError, StudentNotFoundError
from lesson_recommender.domain.models import CollaborativeSignal, Lesson, Student
from lesson_recommender.domain.ports import CatalogRepository, CollaborativeSource
from lesson_recommender.domain.rules import EligibilityPolicy
from lesson_recommender.recommender.candidates import eligible_candidates
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.explain import ExplanationInput, explain

MAX_K = 50


@dataclass(frozen=True, slots=True)
class Weights:
    content: float = 0.5
    collaborative: float = 0.4
    popularity: float = 0.1

    def __post_init__(self) -> None:
        values = (self.content, self.collaborative, self.popularity)
        if any(value < 0 for value in values):
            raise ValueError(f"pesos não podem ser negativos: {values}")
        if sum(values) == 0:
            raise ValueError("ao menos um peso precisa ser positivo")


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Contribuição normalizada (0 a 1) de cada sinal, antes de aplicar os pesos."""

    content: float
    collaborative: float
    popularity: float


@dataclass(frozen=True, slots=True)
class Recommendation:
    lesson: Lesson
    score: float
    breakdown: ScoreBreakdown
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Scored:
    lesson: Lesson
    score: float
    breakdown: ScoreBreakdown


@dataclass(frozen=True, slots=True)
class _Ranking:
    student: Student
    booked: frozenset[str]
    signals: Mapping[str, CollaborativeSignal]
    items: list[_Scored]


def min_max(values: Mapping[str, float]) -> dict[str, float]:
    """Reescala para [0, 1]. Se todos os valores forem iguais, o sinal não discrimina: vira 0."""
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if high == low:
        return dict.fromkeys(values, 0.0)
    return {key: (value - low) / (high - low) for key, value in values.items()}


def share_of_max(values: Mapping[str, float]) -> dict[str, float]:
    """Divide pelo maior valor (preserva o zero como 'nenhuma evidência')."""
    high = max(values.values(), default=0.0)
    if high <= 0:
        return dict.fromkeys(values, 0.0)
    return {key: value / high for key, value in values.items()}


class HybridRecommender:
    def __init__(
        self,
        repository: CatalogRepository,
        collaborative: CollaborativeSource,
        content: ContentModel,
        *,
        weights: Weights | None = None,
        policy: EligibilityPolicy | None = None,
        neighbors: int = 30,
    ) -> None:
        if neighbors <= 0:
            raise ValueError(f"neighbors deve ser positivo: {neighbors}")
        self._repository = repository
        self._collaborative = collaborative
        self._content = content
        self._weights = weights or Weights()
        self._policy = policy or EligibilityPolicy()
        self._neighbors = neighbors

    @property
    def weights(self) -> Weights:
        return self._weights

    def recommend(self, student_id: str, k: int) -> list[Recommendation]:
        """Top-k aulas com pontuação, decomposição por sinal e explicação."""
        ranking = self._rank(student_id, k)
        titles = {lesson.id: lesson.title for lesson in self._repository.list_lessons()}
        return [
            Recommendation(
                lesson=item.lesson,
                score=round(item.score, 6),
                breakdown=item.breakdown,
                reasons=self._reasons(ranking, item, titles),
            )
            for item in ranking.items
        ]

    def rank(self, student_id: str, k: int) -> list[str]:
        """Só os ids, sem explicação: é o que a avaliação offline consome."""
        return [item.lesson.id for item in self._rank(student_id, k).items]

    def _rank(self, student_id: str, k: int) -> _Ranking:
        if not 1 <= k <= MAX_K:
            raise InvalidRequestError(f"k deve estar entre 1 e {MAX_K}: {k}")
        student = self._repository.get_student(student_id)
        if student is None:
            raise StudentNotFoundError(student_id)

        history = self._repository.history(student_id)
        booked = history.booked_lesson_ids
        candidates = eligible_candidates(
            student, self._repository.list_lessons(), history, self._policy
        )
        if not candidates:
            return _Ranking(student, booked, {}, [])
        ids = [lesson.id for lesson in candidates]

        content = min_max(self._content.scores(self._content.profile(student, history), ids))
        signals = self._collaborative_signals(student_id, booked)
        collaborative = share_of_max({i: signals[i].score if i in signals else 0.0 for i in ids})
        raw_popularity = self._repository.popularity()
        popularity = share_of_max({i: float(raw_popularity.get(i, 0)) for i in ids})

        w = self._weights
        items = [
            _Scored(
                lesson=lesson,
                score=w.content * content[lesson.id]
                + w.collaborative * collaborative[lesson.id]
                + w.popularity * popularity[lesson.id],
                breakdown=ScoreBreakdown(
                    content=round(content[lesson.id], 6),
                    collaborative=round(collaborative[lesson.id], 6),
                    popularity=round(popularity[lesson.id], 6),
                ),
            )
            for lesson in candidates
        ]
        items.sort(key=lambda item: (-item.score, item.lesson.id))
        return _Ranking(student, booked, signals, items[:k])

    def _collaborative_signals(
        self, student_id: str, booked: frozenset[str]
    ) -> Mapping[str, CollaborativeSignal]:
        if self._weights.collaborative == 0 or not booked:
            return {}
        return self._collaborative.neighbor_scores(student_id, neighbors=self._neighbors)

    def _reasons(
        self, ranking: _Ranking, item: _Scored, titles: Mapping[str, str]
    ) -> tuple[str, ...]:
        content_active = self._weights.content > 0
        similar = self._content.most_similar(item.lesson.id, ranking.booked)
        popularity_share = item.breakdown.popularity if self._weights.popularity > 0 else 0.0
        return explain(
            ExplanationInput(
                student=ranking.student,
                lesson=item.lesson,
                content_active=content_active,
                similar_lesson_title=titles.get(similar[0]) if similar else None,
                similar_lesson_score=similar[1] if similar else 0.0,
                collaborative=ranking.signals.get(item.lesson.id),
                popularity_share=popularity_share,
            )
        )
