"""Entidades do domínio: aulas, alunos e interações de um estúdio de yoga e pilates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum


class Level(IntEnum):
    """Nível técnico. ALL representa aulas abertas a todos os níveis ("livre")."""

    ALL = 0
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3

    @property
    def label(self) -> str:
        return _LEVEL_LABELS[self]


_LEVEL_LABELS = {
    Level.ALL: "livre",
    Level.BEGINNER: "iniciante",
    Level.INTERMEDIATE: "intermediário",
    Level.ADVANCED: "avançado",
}


class Goal(StrEnum):
    FLEXIBILITY = "flexibilidade"
    STRENGTH = "fortalecimento"
    STRESS_RELIEF = "reducao_estresse"
    POSTURE = "postura"
    CONDITIONING = "condicionamento"
    REHABILITATION = "reabilitacao"

    @property
    def label(self) -> str:
        return _GOAL_LABELS[self]


_GOAL_LABELS = {
    Goal.FLEXIBILITY: "flexibilidade",
    Goal.STRENGTH: "fortalecimento",
    Goal.STRESS_RELIEF: "redução do estresse",
    Goal.POSTURE: "postura",
    Goal.CONDITIONING: "condicionamento",
    Goal.REHABILITATION: "reabilitação",
}


class Restriction(StrEnum):
    PREGNANCY = "gestante"
    LOWER_BACK_INJURY = "lesao_lombar"
    HYPERTENSION = "hipertensao"
    KNEE_INJURY = "lesao_joelho"


class DayPeriod(StrEnum):
    MORNING = "manha"
    AFTERNOON = "tarde"
    EVENING = "noite"

    @property
    def label(self) -> str:
        return {"manha": "manhã", "tarde": "tarde", "noite": "noite"}[self.value]

    @staticmethod
    def from_time(start_time: str) -> DayPeriod:
        hour = int(start_time.split(":", maxsplit=1)[0])
        if hour < 12:
            return DayPeriod.MORNING
        if hour < 17:
            return DayPeriod.AFTERNOON
        return DayPeriod.EVENING


WEEKDAY_LABELS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True, slots=True)
class Modality:
    id: str
    name: str
    family: str


@dataclass(frozen=True, slots=True)
class Instructor:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Lesson:
    """Aula recorrente da grade (ex.: Hatha Yoga, terça 07:00, com uma instrutora)."""

    id: str
    title: str
    modality_id: str
    instructor_id: str
    level: Level
    weekday: int
    start_time: str
    duration_minutes: int
    intensity: int
    capacity: int
    booked_seats: int
    description: str
    focus: frozenset[Goal]
    contraindications: frozenset[Restriction]

    def __post_init__(self) -> None:
        if not 1 <= self.intensity <= 5:
            raise ValueError(f"intensidade deve estar entre 1 e 5: {self.intensity}")
        if not 0 <= self.weekday <= 6:
            raise ValueError(f"dia da semana inválido: {self.weekday}")
        if self.capacity <= 0:
            raise ValueError(f"capacidade deve ser positiva: {self.capacity}")
        if not 0 <= self.booked_seats <= self.capacity:
            raise ValueError(f"vagas ocupadas fora do intervalo: {self.booked_seats}")

    @property
    def is_full(self) -> bool:
        return self.booked_seats >= self.capacity

    @property
    def period(self) -> DayPeriod:
        return DayPeriod.from_time(self.start_time)

    @property
    def schedule_label(self) -> str:
        return f"{WEEKDAY_LABELS[self.weekday]} {self.start_time}"


@dataclass(frozen=True, slots=True)
class Student:
    id: str
    name: str
    level: Level
    goals: tuple[Goal, ...]
    restrictions: frozenset[Restriction]

    def __post_init__(self) -> None:
        if self.level is Level.ALL:
            raise ValueError("aluno precisa de um nível concreto, não 'livre'")


@dataclass(frozen=True, slots=True)
class Booking:
    student_id: str
    lesson_id: str
    booked_at: datetime


@dataclass(frozen=True, slots=True)
class Rating:
    student_id: str
    lesson_id: str
    score: int
    rated_at: datetime

    def __post_init__(self) -> None:
        if not 1 <= self.score <= 5:
            raise ValueError(f"nota deve estar entre 1 e 5: {self.score}")


@dataclass(frozen=True, slots=True)
class Dataset:
    """Fotografia completa do estúdio: catálogo, alunos e histórico de interações."""

    modalities: tuple[Modality, ...]
    instructors: tuple[Instructor, ...]
    lessons: tuple[Lesson, ...]
    students: tuple[Student, ...]
    bookings: tuple[Booking, ...]
    ratings: tuple[Rating, ...]


@dataclass(frozen=True, slots=True)
class StudentHistory:
    """Histórico agregado de um aluno: reservas por aula e última nota dada a cada aula."""

    bookings: Mapping[str, int]
    ratings: Mapping[str, int]

    @property
    def booked_lesson_ids(self) -> frozenset[str]:
        return frozenset(self.bookings)


@dataclass(frozen=True, slots=True)
class CollaborativeSignal:
    """Evidência colaborativa para uma aula: pontuação somada e quantos vizinhos a sustentam."""

    score: float
    support: int
