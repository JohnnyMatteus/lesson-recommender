"""Repositório em memória: implementa catálogo e colaborativo a partir de um `Dataset`.

Usado nos testes, na avaliação offline (com o recorte de treino) e na API sem Neo4j.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from lesson_recommender.domain.models import (
    CollaborativeSignal,
    Dataset,
    Instructor,
    Lesson,
    Modality,
    Student,
    StudentHistory,
)
from lesson_recommender.recommender.collaborative import neighborhood_scores


class InMemoryRepository:
    def __init__(self, dataset: Dataset) -> None:
        self._students = {student.id: student for student in dataset.students}
        self._lessons = tuple(sorted(dataset.lessons, key=lambda lesson: lesson.id))
        self._modalities = {modality.id: modality for modality in dataset.modalities}
        self._instructors = {instructor.id: instructor for instructor in dataset.instructors}

        counts: dict[str, Counter[str]] = {}
        for booking in dataset.bookings:
            counts.setdefault(booking.student_id, Counter())[booking.lesson_id] += 1
        self._booking_counts = counts
        self._booked_sets = {student: frozenset(c) for student, c in counts.items()}

        # Ordenar por data garante que a última nota de cada par (aluno, aula) prevaleça.
        self._ratings: dict[tuple[str, str], int] = {}
        self._ratings_by_student: dict[str, dict[str, int]] = {}
        for rating in sorted(dataset.ratings, key=lambda r: r.rated_at):
            self._ratings[(rating.student_id, rating.lesson_id)] = rating.score
            self._ratings_by_student.setdefault(rating.student_id, {})[rating.lesson_id] = (
                rating.score
            )

        popularity: Counter[str] = Counter()
        for lessons in self._booked_sets.values():
            popularity.update(lessons)
        self._popularity = dict(popularity)

    def get_student(self, student_id: str) -> Student | None:
        return self._students.get(student_id)

    def list_lessons(self) -> Sequence[Lesson]:
        return self._lessons

    def modalities(self) -> Mapping[str, Modality]:
        return self._modalities

    def instructors(self) -> Mapping[str, Instructor]:
        return self._instructors

    def history(self, student_id: str) -> StudentHistory:
        bookings = dict(self._booking_counts.get(student_id, Counter()))
        ratings = dict(self._ratings_by_student.get(student_id, {}))
        return StudentHistory(bookings=bookings, ratings=ratings)

    def popularity(self) -> Mapping[str, int]:
        return self._popularity

    def neighbor_scores(
        self, student_id: str, *, neighbors: int
    ) -> Mapping[str, CollaborativeSignal]:
        return neighborhood_scores(
            student_id, self._booked_sets, self._ratings, neighbors=neighbors
        )
