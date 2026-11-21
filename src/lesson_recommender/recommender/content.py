"""Similaridade de conteúdo: aulas e alunos no mesmo espaço de embeddings."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

import numpy as np

from lesson_recommender.domain.models import (
    Goal,
    Instructor,
    Lesson,
    Modality,
    Student,
    StudentHistory,
)
from lesson_recommender.domain.ports import EmbeddingProvider, Vector
from lesson_recommender.domain.vocabulary import GOAL_QUERIES

_INTENSITY_WORDS = {1: "muito leve", 2: "leve", 3: "moderada", 4: "intensa", 5: "muito intensa"}


def lesson_document(lesson: Lesson, modality: Modality, instructor: Instructor) -> str:
    """Texto que representa a aula para o modelo de conteúdo."""
    return (
        f"{lesson.title}. {modality.name} ({modality.family}). Nível {lesson.level.label}. "
        f"Intensidade {_INTENSITY_WORDS[lesson.intensity]}. Aula da {lesson.period.label} "
        f"com {instructor.name}. {lesson.description}"
    )


def _normalize(vector: Vector) -> Vector:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else vector


class ContentModel:
    """Pré-calcula os vetores das aulas e monta o perfil do aluno sob demanda.

    Perfil = combinação dos objetivos declarados (peso `goal_weight`) com a média das aulas já
    reservadas, ponderada por frequência (1 + log) e pela nota dada (nota/3; sem nota, 1).
    """

    def __init__(
        self,
        embedder: EmbeddingProvider,
        lessons: Sequence[Lesson],
        modalities: Mapping[str, Modality],
        instructors: Mapping[str, Instructor],
        *,
        goal_weight: float = 0.4,
    ) -> None:
        if not 0.0 <= goal_weight <= 1.0:
            raise ValueError(f"goal_weight deve estar em [0, 1]: {goal_weight}")
        self._goal_weight = goal_weight
        self._index = {lesson.id: row for row, lesson in enumerate(lessons)}
        documents = [
            lesson_document(
                lesson, modalities[lesson.modality_id], instructors[lesson.instructor_id]
            )
            for lesson in lessons
        ]
        self._matrix = embedder.embed(documents)
        goals = list(Goal)
        goal_matrix = embedder.embed([GOAL_QUERIES[goal] for goal in goals])
        self._goal_vectors = {goal: goal_matrix[row] for row, goal in enumerate(goals)}

    def profile(self, student: Student, history: StudentHistory) -> Vector:
        dimensions = self._matrix.shape[1]
        goal_vector = np.zeros(dimensions)
        for goal in student.goals:
            goal_vector += self._goal_vectors[goal]
        goal_vector = _normalize(goal_vector)

        history_vector = np.zeros(dimensions)
        for lesson_id, count in history.bookings.items():
            row = self._index.get(lesson_id)
            if row is None:
                continue
            rating_factor = (
                history.ratings[lesson_id] / 3.0 if lesson_id in history.ratings else 1.0
            )
            history_vector += (1.0 + math.log(count)) * rating_factor * self._matrix[row]
        history_vector = _normalize(history_vector)

        if not history_vector.any():
            return goal_vector
        return _normalize(
            self._goal_weight * goal_vector + (1.0 - self._goal_weight) * history_vector
        )

    def scores(self, profile: Vector, lesson_ids: Iterable[str]) -> dict[str, float]:
        return {
            lesson_id: float(self._matrix[self._index[lesson_id]] @ profile)
            for lesson_id in lesson_ids
        }

    def most_similar(self, lesson_id: str, among: Iterable[str]) -> tuple[str, float] | None:
        """Aula de `among` mais parecida com `lesson_id` (usada para explicar a recomendação)."""
        target = self._matrix[self._index[lesson_id]]
        best: tuple[str, float] | None = None
        for other in sorted(among):
            row = self._index.get(other)
            if row is None or other == lesson_id:
                continue
            similarity = float(self._matrix[row] @ target)
            if best is None or similarity > best[1]:
                best = (other, similarity)
        return best
