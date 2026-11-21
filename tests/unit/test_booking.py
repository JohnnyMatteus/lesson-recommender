from datetime import UTC, datetime

import fakeredis
import pytest

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.adapters.redis_cache import RedisRecommendationCache, cache_key
from lesson_recommender.application.booking import BookLesson
from lesson_recommender.domain.errors import (
    BookingRejectedError,
    LessonNotFoundError,
    StudentNotFoundError,
)
from tests.factories import studio

NOW = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository(studio())


def test_booking_occupies_seat_updates_history_and_invalidates_cache(
    repo: InMemoryRepository,
) -> None:
    client = fakeredis.FakeRedis()
    client.hset(cache_key("eva"), "5", "[]")
    use_case = BookLesson(
        repo, repo, RedisRecommendationCache(client, ttl_seconds=60), clock=lambda: NOW
    )

    booking = use_case.execute("eva", "y2")

    assert booking.booked_at == NOW
    assert repo.history("eva").bookings == {"y2": 1}
    assert next(x for x in repo.list_lessons() if x.id == "y2").booked_seats == 1
    assert repo.popularity()["y2"] == 2
    assert not client.exists(cache_key("eva"))


@pytest.mark.parametrize(
    ("student_id", "lesson_id", "reason"),
    [("eva", "y3", "lotada"), ("eva", "p1", "fora_do_nivel"), ("duda", "x1", "contraindicada")],
)
def test_hard_rules_reject_booking(
    repo: InMemoryRepository, student_id: str, lesson_id: str, reason: str
) -> None:
    with pytest.raises(BookingRejectedError) as error:
        BookLesson(repo, repo).execute(student_id, lesson_id)
    assert error.value.reason == reason
    assert lesson_id not in repo.history(student_id).bookings


def test_unknown_student_or_lesson(repo: InMemoryRepository) -> None:
    with pytest.raises(StudentNotFoundError):
        BookLesson(repo, repo).execute("ninguem", "y1")
    with pytest.raises(LessonNotFoundError):
        BookLesson(repo, repo).execute("eva", "nenhuma")
