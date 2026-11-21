"""Baselines: o mínimo que o modelo híbrido precisa vencer para justificar a complexidade."""

from __future__ import annotations

import random
from typing import Protocol

from lesson_recommender.domain.errors import StudentNotFoundError
from lesson_recommender.domain.ports import CatalogRepository
from lesson_recommender.domain.rules import EligibilityPolicy
from lesson_recommender.recommender.candidates import eligible_candidates


class RankingModel(Protocol):
    def rank(self, student_id: str, k: int) -> list[str]: ...


class _CandidateModel:
    def __init__(self, repository: CatalogRepository, policy: EligibilityPolicy) -> None:
        self._repository = repository
        self._policy = policy

    def _candidates(self, student_id: str) -> list[str]:
        student = self._repository.get_student(student_id)
        if student is None:
            raise StudentNotFoundError(student_id)
        lessons = eligible_candidates(
            student,
            self._repository.list_lessons(),
            self._repository.history(student_id),
            self._policy,
        )
        return [lesson.id for lesson in lessons]


class PopularityRecommender(_CandidateModel):
    """Aulas com mais alunos distintos no treino (empate: id)."""

    def rank(self, student_id: str, k: int) -> list[str]:
        popularity = self._repository.popularity()
        candidates = self._candidates(student_id)
        return sorted(candidates, key=lambda i: (-popularity.get(i, 0), i))[:k]


class RandomRecommender(_CandidateModel):
    """Ordem aleatória, mas reprodutível: a semente combina a seed global e o id do aluno."""

    def __init__(
        self, repository: CatalogRepository, policy: EligibilityPolicy, *, seed: int
    ) -> None:
        super().__init__(repository, policy)
        self._seed = seed

    def rank(self, student_id: str, k: int) -> list[str]:
        candidates = self._candidates(student_id)
        random.Random(f"{self._seed}:{student_id}").shuffle(candidates)
        return candidates[:k]
