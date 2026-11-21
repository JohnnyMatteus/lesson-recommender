"""Camada anticorrupção: traduz o modelo do SaaS para o modelo do recomendador.

Diferenças que a tradução resolve:
- o SaaS tem *sessões* datadas; o recomendador tem *aulas recorrentes*. Uma série vira uma
  aula (id = `series_id`) e as reservas de todas as suas sessões contam para ela;
- o SaaS não guarda nível, objetivos nem restrições do aluno. Nível e objetivos são inferidos
  do histórico de reservas; restrições de saúde nunca são inferidas (ficam vazias);
- só reserva `confirmed` é sinal de interesse; lista de espera e cancelamento não contam.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime

from lesson_recommender.domain.models import (
    Booking,
    Dataset,
    Goal,
    Instructor,
    Lesson,
    Level,
    Modality,
    Student,
)
from lesson_recommender.saas.catalog import (
    FALLBACK_MODALITY,
    level_from_title,
    match_rule,
)
from lesson_recommender.saas.payloads import SaasBooking, SaasSession

CONFIRMED = "confirmed"
MAX_INFERRED_GOALS = 2
_GOAL_ORDER = {goal: position for position, goal in enumerate(Goal)}


def lesson_key(session: SaasSession) -> str:
    return session.series_id or session.id


def _lesson_from_sessions(sessions: Sequence[SaasSession], now: datetime) -> Lesson:
    ordered = sorted(sessions, key=lambda s: (s.starts_at, s.id))
    upcoming = [s for s in ordered if s.starts_at >= now]
    # A ocupação que importa é a da próxima turma; sem futura, a mais recente.
    reference = upcoming[0] if upcoming else ordered[-1]
    local = reference.starts_at_local
    rule = match_rule(reference.title)
    capacity = max(reference.capacity, 1)
    return Lesson(
        id=lesson_key(reference),
        title=reference.title,
        modality_id=(rule.modality if rule else FALLBACK_MODALITY).id,
        instructor_id=reference.instructor.id,
        level=level_from_title(reference.title),
        weekday=local.weekday(),
        start_time=local.strftime("%H:%M"),
        duration_minutes=max(
            1, round((reference.ends_at - reference.starts_at).total_seconds() / 60)
        ),
        intensity=rule.intensity if rule else 3,
        capacity=capacity,
        booked_seats=min(max(reference.confirmed_count, 0), capacity),
        description=rule.description if rule else reference.title,
        focus=rule.focus if rule else frozenset(),
        contraindications=rule.contraindications if rule else frozenset(),
    )


def infer_student(student_id: str, name: str, booked: Iterable[Lesson]) -> Student:
    lessons = list(booked)
    levels = [lesson.level for lesson in lessons if lesson.level is not Level.ALL]
    level = max(levels, default=Level.BEGINNER)
    focus = Counter(goal for lesson in lessons for goal in lesson.focus)
    ranked = sorted(focus, key=lambda g: (-focus[g], _GOAL_ORDER[g]))
    return Student(
        id=student_id,
        name=name,
        level=level,
        goals=tuple(ranked[:MAX_INFERRED_GOALS]),
        restrictions=frozenset(),
    )


def translate(
    sessions: Sequence[SaasSession], bookings: Sequence[SaasBooking], *, now: datetime
) -> Dataset:
    """Monta o `Dataset` do recomendador a partir do que o SaaS devolveu para um tenant."""
    by_series: dict[str, list[SaasSession]] = defaultdict(list)
    for session in sessions:
        by_series[lesson_key(session)].append(session)
    lessons = {key: _lesson_from_sessions(group, now) for key, group in by_series.items()}
    series_of = {session.id: lesson_key(session) for session in sessions}

    domain_bookings: list[Booking] = []
    names: dict[str, str] = {}
    for booking in bookings:
        series = series_of.get(booking.session_id)
        if booking.status != CONFIRMED or series is None:
            continue
        names[booking.member.id] = booking.member.name
        domain_bookings.append(
            Booking(booking.member.id, series, booking.confirmed_at or booking.queued_at)
        )
    domain_bookings.sort(key=lambda b: (b.booked_at, b.student_id, b.lesson_id))

    booked_by_student: dict[str, list[Lesson]] = defaultdict(list)
    for entry in domain_bookings:
        booked_by_student[entry.student_id].append(lessons[entry.lesson_id])
    students = tuple(
        infer_student(student_id, names[student_id], booked_by_student[student_id])
        for student_id in sorted(booked_by_student)
    )

    modalities: dict[str, Modality] = {}
    instructors: dict[str, Instructor] = {}
    for session in sessions:
        rule = match_rule(session.title)
        modality = rule.modality if rule else FALLBACK_MODALITY
        modalities[modality.id] = modality
        instructors[session.instructor.id] = Instructor(
            session.instructor.id, session.instructor.name
        )
    return Dataset(
        modalities=tuple(sorted(modalities.values(), key=lambda m: m.id)),
        instructors=tuple(sorted(instructors.values(), key=lambda i: i.id)),
        lessons=tuple(sorted(lessons.values(), key=lambda lesson: lesson.id)),
        students=students,
        bookings=tuple(domain_bookings),
        ratings=(),
    )
