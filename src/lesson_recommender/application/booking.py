"""Caso de uso: registrar a reserva de uma aula e invalidar as recomendações do aluno."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from lesson_recommender.domain.errors import (
    BookingRejectedError,
    LessonNotFoundError,
    StudentNotFoundError,
)
from lesson_recommender.domain.models import Booking
from lesson_recommender.domain.ports import BookingRepository, CatalogRepository
from lesson_recommender.domain.rules import EligibilityPolicy, Rejection, rejection_reason
from lesson_recommender.recommender.ports import RecommendationCache


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BookLesson:
    """As mesmas regras duras da recomendação valem para a reserva (ADR 0005)."""

    def __init__(
        self,
        catalog: CatalogRepository,
        bookings: BookingRepository,
        cache: RecommendationCache | None = None,
        *,
        policy: EligibilityPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._catalog = catalog
        self._bookings = bookings
        self._cache = cache
        self._policy = policy or EligibilityPolicy()
        self._clock = clock

    def execute(self, student_id: str, lesson_id: str) -> Booking:
        student = self._catalog.get_student(student_id)
        if student is None:
            raise StudentNotFoundError(student_id)
        lesson = next((x for x in self._catalog.list_lessons() if x.id == lesson_id), None)
        if lesson is None:
            raise LessonNotFoundError(lesson_id)
        reason = rejection_reason(student, lesson, self._policy)
        if reason is not None:
            raise BookingRejectedError(lesson_id, reason.value)

        booking = Booking(student_id, lesson_id, self._clock())
        if not self._bookings.record_booking(student_id, lesson_id, booking.booked_at):
            raise BookingRejectedError(lesson_id, Rejection.FULL.value)
        if self._cache is not None:
            self._cache.invalidate(student_id)
        return booking
