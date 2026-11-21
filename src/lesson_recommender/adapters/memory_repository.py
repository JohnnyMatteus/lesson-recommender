"""Repositório em memória: implementa catálogo e colaborativo a partir de um `Dataset`.

Usado nos testes, na avaliação offline (com o recorte de treino) e na API sem Neo4j.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime

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

    def record_booking(self, student_id: str, lesson_id: str, booked_at: datetime) -> bool:
        index = next(i for i, lesson in enumerate(self._lessons) if lesson.id == lesson_id)
        lesson = self._lessons[index]
        if lesson.is_full:
            return False
        lessons = list(self._lessons)
        lessons[index] = replace(lesson, booked_seats=lesson.booked_seats + 1)
        self._lessons = tuple(lessons)
        counts = self._booking_counts.setdefault(student_id, Counter())
        if lesson_id not in counts:
            self._popularity[lesson_id] = self._popularity.get(lesson_id, 0) + 1
        counts[lesson_id] += 1
        self._booked_sets[student_id] = frozenset(counts)
        return True

    def neighbor_scores(
        self, student_id: str, *, neighbors: int
    ) -> Mapping[str, CollaborativeSignal]:
        return neighborhood_scores(
            student_id, self._booked_sets, self._ratings, neighbors=neighbors
        )
