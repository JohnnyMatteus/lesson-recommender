import pytest

from lesson_recommender.domain.models import Level, Restriction
from lesson_recommender.domain.rules import (
    EligibilityPolicy,
    Rejection,
    is_eligible,
    level_fits,
    rejection_reason,
)
from tests.factories import lesson, student


@pytest.mark.parametrize(
    ("student_level", "lesson_level", "expected"),
    [
        (Level.BEGINNER, Level.ALL, True),
        (Level.BEGINNER, Level.BEGINNER, True),
        (Level.BEGINNER, Level.INTERMEDIATE, False),
        (Level.INTERMEDIATE, Level.BEGINNER, True),
        (Level.ADVANCED, Level.INTERMEDIATE, True),
        (Level.ADVANCED, Level.BEGINNER, False),
        (Level.BEGINNER, Level.ADVANCED, False),
    ],
)
def test_level_fits(student_level: Level, lesson_level: Level, expected: bool) -> None:
    assert level_fits(student_level, lesson_level) is expected


def test_full_lesson_is_rejected() -> None:
    full = lesson("l", capacity=8, booked_seats=8)
    assert rejection_reason(student("s"), full, EligibilityPolicy()) is Rejection.FULL


def test_capacity_rule_can_be_disabled_for_offline_evaluation() -> None:
    full = lesson("l", capacity=8, booked_seats=8)
    assert is_eligible(student("s"), full, EligibilityPolicy(enforce_capacity=False))


def test_lesson_above_student_level_is_rejected() -> None:
    hard = lesson("l", level=Level.ADVANCED)
    assert rejection_reason(student("s"), hard, EligibilityPolicy()) is Rejection.LEVEL_MISMATCH


def test_contraindication_wins_over_other_reasons() -> None:
    risky = lesson(
        "l",
        level=Level.ADVANCED,
        booked_seats=10,
        contraindications=frozenset({Restriction.HYPERTENSION}),
    )
    hypertensive = student("s", restrictions=frozenset({Restriction.HYPERTENSION}))
    assert rejection_reason(hypertensive, risky, EligibilityPolicy()) is Rejection.CONTRAINDICATED


def test_eligible_lesson_has_no_rejection() -> None:
    assert rejection_reason(student("s"), lesson("l"), EligibilityPolicy()) is None
