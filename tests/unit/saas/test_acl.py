from datetime import UTC, datetime

from lesson_recommender.domain.models import Goal, Level
from lesson_recommender.saas.acl import translate
from lesson_recommender.saas.payloads import SaasBooking, SaasSession
from tests.unit.saas.saas_fakes import NOW, booking, session


def _sessions(*items: dict[str, object]) -> list[SaasSession]:
    return [SaasSession.model_validate(i) for i in items]


def _bookings(*items: dict[str, object]) -> list[SaasBooking]:
    return [SaasBooking.model_validate(i) for i in items]


def test_sessions_of_a_series_become_one_recurring_lesson() -> None:
    dataset = translate(
        _sessions(
            session("s1", "ser-1", "Vinyasa Flow", "2026-11-10T10:00:00Z", confirmed=9),
            session("s2", "ser-1", "Vinyasa Flow", "2026-11-24T10:00:00Z", confirmed=4),
        ),
        [],
        now=NOW,
    )
    [lesson] = dataset.lessons
    assert lesson.id == "ser-1"
    assert lesson.modality_id == "vinyasa"
    assert (lesson.weekday, lesson.start_time) == (1, "07:00")  # terça, horário local
    assert lesson.duration_minutes == 60
    # ocupação da próxima turma, não da passada
    assert lesson.booked_seats == 4


def test_only_confirmed_bookings_are_signal() -> None:
    dataset = translate(
        _sessions(session("s1", "ser-1", "Hatha Yoga", "2026-11-10T10:00:00Z")),
        _bookings(
            booking("b1", "s1", "m1"),
            booking("b2", "s1", "m2", "waitlisted"),
            booking("b3", "s1", "m3", "canceled"),
            booking("b4", "desconhecida", "m4"),
        ),
        now=NOW,
    )
    assert [b.student_id for b in dataset.bookings] == ["m1"]
    assert [s.id for s in dataset.students] == ["m1"]
    assert dataset.bookings[0].lesson_id == "ser-1"
    assert dataset.bookings[0].booked_at == datetime(2026, 11, 10, 9, 0, 1, tzinfo=UTC)


def test_student_level_and_goals_are_inferred_from_history_and_never_restrictions() -> None:
    dataset = translate(
        _sessions(
            session("s1", "a", "Yin Yoga iniciante", "2026-11-10T10:00:00Z"),
            session("s2", "b", "Ashtanga avançado", "2026-11-11T10:00:00Z"),
        ),
        _bookings(booking("b1", "s1", "m1"), booking("b2", "s2", "m1")),
        now=NOW,
    )
    [student] = dataset.students
    assert student.level is Level.ADVANCED
    assert len(student.goals) == 2
    assert Goal.FLEXIBILITY in student.goals or Goal.STRESS_RELIEF in student.goals
    assert student.restrictions == frozenset()


def test_unknown_titles_fall_back_to_neutral_lesson() -> None:
    dataset = translate(
        _sessions(session("s1", None, "Aula especial", "2026-11-10T10:00:00Z", confirmed=99)),
        [],
        now=NOW,
    )
    [lesson] = dataset.lessons
    assert lesson.id == "s1"
    assert lesson.level is Level.ALL
    assert lesson.focus == frozenset()
    assert lesson.booked_seats == lesson.capacity  # lotação limitada à capacidade
