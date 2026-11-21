"""Construtores de entidades para testes, com valores padrão explícitos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from lesson_recommender.domain.models import (
    Booking,
    Dataset,
    Goal,
    Instructor,
    Lesson,
    Level,
    Modality,
    Rating,
    Restriction,
    Student,
)

T0 = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)


def lesson(lesson_id: str, **overrides: Any) -> Lesson:
    values: dict[str, Any] = {
        "id": lesson_id,
        "title": f"Aula {lesson_id}",
        "modality_id": "hatha",
        "instructor_id": "inst-1",
        "level": Level.BEGINNER,
        "weekday": 0,
        "start_time": "07:00",
        "duration_minutes": 60,
        "intensity": 2,
        "capacity": 10,
        "booked_seats": 0,
        "description": "Foco em alongamento profundo e respiração consciente.",
        "focus": frozenset({Goal.FLEXIBILITY}),
        "contraindications": frozenset(),
    }
    values.update(overrides)
    return Lesson(**values)


def student(student_id: str, **overrides: Any) -> Student:
    values: dict[str, Any] = {
        "id": student_id,
        "name": f"Aluno {student_id}",
        "level": Level.BEGINNER,
        "goals": (Goal.FLEXIBILITY,),
        "restrictions": frozenset(),
    }
    values.update(overrides)
    return Student(**values)


def booking(student_id: str, lesson_id: str, day: int = 0) -> Booking:
    return Booking(student_id, lesson_id, T0 + timedelta(days=day))


def rating(student_id: str, lesson_id: str, score: int, day: int = 0) -> Rating:
    return Rating(student_id, lesson_id, score, T0 + timedelta(days=day, hours=2))


MODALITIES = (
    Modality("hatha", "Hatha Yoga", "yoga"),
    Modality("pilates-solo", "Pilates Solo", "pilates"),
)
INSTRUCTORS = (Instructor("inst-1", "Celina Toledo"), Instructor("inst-2", "Dario Meireles"))


def studio() -> Dataset:
    """Estúdio mínimo, com casos para cada regra de negócio.

    - y1, y2, y3: yoga iniciante de flexibilidade (y3 lotada).
    - p1: pilates intermediário de fortalecimento.
    - x1: aula avançada intensa, contraindicada para gestantes.
    - ana e bia gostam de yoga; bia também fez y2. caio faz pilates.
    """
    lessons = (
        lesson("y1"),
        lesson("y2", start_time="18:30"),
        lesson("y3", booked_seats=10),
        lesson(
            "p1",
            modality_id="pilates-solo",
            instructor_id="inst-2",
            level=Level.INTERMEDIATE,
            intensity=3,
            description="Foco em fortalecimento do core e alinhamento postural.",
            focus=frozenset({Goal.STRENGTH, Goal.POSTURE}),
        ),
        lesson(
            "x1",
            level=Level.ADVANCED,
            intensity=5,
            description="Série vigorosa de força.",
            focus=frozenset({Goal.STRENGTH}),
            contraindications=frozenset({Restriction.PREGNANCY}),
        ),
    )
    students = (
        student("ana"),
        student("bia"),
        student("caio", level=Level.INTERMEDIATE, goals=(Goal.STRENGTH,)),
        student("duda", level=Level.ADVANCED, restrictions=frozenset({Restriction.PREGNANCY})),
        student("eva"),
    )
    bookings = (
        booking("ana", "y1", 0),
        booking("ana", "y1", 7),
        booking("bia", "y1", 1),
        booking("bia", "y2", 2),
        booking("caio", "p1", 1),
        booking("duda", "p1", 3),
    )
    ratings = (rating("bia", "y2", 5, 2),)
    return Dataset(MODALITIES, INSTRUCTORS, lessons, students, bookings, ratings)
