import pytest

from lesson_recommender.domain.models import DayPeriod, Level, Rating
from tests.factories import T0, lesson, student


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"intensity": 0}, "intensidade"),
        ({"intensity": 6}, "intensidade"),
        ({"weekday": 7}, "dia da semana"),
        ({"capacity": 0}, "capacidade"),
        ({"booked_seats": 11}, "vagas"),
    ],
)
def test_lesson_rejects_invalid_values(overrides: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        lesson("l", **overrides)


def test_student_needs_concrete_level() -> None:
    with pytest.raises(ValueError, match="nível concreto"):
        student("s", level=Level.ALL)


@pytest.mark.parametrize("score", [0, 6])
def test_rating_score_must_be_between_one_and_five(score: int) -> None:
    with pytest.raises(ValueError, match="nota"):
        Rating("s", "l", score, T0)


@pytest.mark.parametrize(
    ("start", "period"),
    [("06:30", DayPeriod.MORNING), ("12:00", DayPeriod.AFTERNOON), ("17:30", DayPeriod.EVENING)],
)
def test_period_from_start_time(start: str, period: DayPeriod) -> None:
    assert lesson("l", start_time=start).period is period


def test_schedule_label_and_full_flag() -> None:
    full = lesson("l", weekday=1, start_time="07:00", capacity=5, booked_seats=5)
    assert full.schedule_label == "terça 07:00"
    assert full.is_full
