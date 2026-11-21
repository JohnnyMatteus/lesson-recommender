"""Gerador de dataset sintético reprodutível (seed fixa) para um estúdio fictício.

Padrões plantados para que exista sinal a ser aprendido (detalhes em docs/design-doc.md):

1. Objetivos: o aluno prefere aulas cujo foco coincide com seus objetivos (sinal de conteúdo).
2. Turmas latentes ("tribos"): grupos de alunos com instrutores, modalidades e período do dia
   favoritos em comum. Só parte disso aparece no texto; o resto é sinal colaborativo.
3. Período do dia: cada aluno tem um período preferido (manhã, tarde ou noite).
4. Descoberta gradual: o aluno começa com poucas aulas e descobre novas ao longo das semanas,
   escolhidas pela afinidade. É o que o split temporal mede.
5. Avaliações: notas correlacionadas com a afinidade, mais ruído.

Os alunos só reservam aulas que passam nas regras de nível e de contraindicação.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from lesson_recommender.domain.models import (
    Booking,
    Dataset,
    DayPeriod,
    Goal,
    Instructor,
    Lesson,
    Level,
    Modality,
    Rating,
    Restriction,
    Student,
)
from lesson_recommender.domain.rules import level_fits


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    seed: int = 42
    lessons: int = 80
    students: int = 400
    instructors: int = 12
    tribes: int = 8
    weeks: int = 26
    start: datetime = datetime(2026, 3, 2, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _ModalitySpec:
    id: str
    name: str
    family: str
    base_intensity: int
    focus: tuple[Goal, ...]
    style: str


MODALITIES = (
    _ModalitySpec(
        "hatha",
        "Hatha Yoga",
        "yoga",
        2,
        (Goal.FLEXIBILITY, Goal.POSTURE, Goal.STRESS_RELIEF),
        "Posturas clássicas sustentadas com atenção ao alinhamento.",
    ),
    _ModalitySpec(
        "vinyasa",
        "Vinyasa Flow",
        "yoga",
        4,
        (Goal.CONDITIONING, Goal.STRENGTH, Goal.FLEXIBILITY),
        "Transições contínuas sincronizadas com a respiração.",
    ),
    _ModalitySpec(
        "yin",
        "Yin Yoga",
        "yoga",
        1,
        (Goal.FLEXIBILITY, Goal.STRESS_RELIEF),
        "Posturas passivas longas no solo, trabalhando tecidos profundos.",
    ),
    _ModalitySpec(
        "ashtanga",
        "Ashtanga",
        "yoga",
        5,
        (Goal.STRENGTH, Goal.CONDITIONING),
        "Série fixa e vigorosa, com contagem de respirações.",
    ),
    _ModalitySpec(
        "restaurativa",
        "Yoga Restaurativa",
        "yoga",
        1,
        (Goal.STRESS_RELIEF, Goal.REHABILITATION),
        "Uso de apoios e almofadas para descanso ativo.",
    ),
    _ModalitySpec(
        "pilates-solo",
        "Pilates Solo",
        "pilates",
        3,
        (Goal.STRENGTH, Goal.POSTURE),
        "Exercícios no tapete com bola, faixa elástica e anel.",
    ),
    _ModalitySpec(
        "pilates-aparelhos",
        "Pilates Aparelhos",
        "pilates",
        3,
        (Goal.POSTURE, Goal.REHABILITATION, Goal.STRENGTH),
        "Reformer, cadillac e chair com molas ajustáveis.",
    ),
)

FOCUS_PHRASES: dict[Goal, tuple[str, ...]] = {
    Goal.FLEXIBILITY: ("alongamento profundo", "mobilidade articular", "flexibilidade de quadril"),
    Goal.STRENGTH: (
        "fortalecimento do core",
        "força de membros superiores",
        "resistência muscular",
    ),
    Goal.STRESS_RELIEF: ("respiração consciente", "relaxamento guiado", "redução do estresse"),
    Goal.POSTURE: ("alinhamento postural", "consciência corporal", "estabilidade da coluna"),
    Goal.CONDITIONING: (
        "ritmo dinâmico",
        "condicionamento cardiorrespiratório",
        "sequências fluidas",
    ),
    Goal.REHABILITATION: (
        "movimentos de baixo impacto",
        "reabilitação funcional",
        "progressão segura",
    ),
}

_FIRST_NAMES = (
    "Aurora",
    "Benício",
    "Celina",
    "Dario",
    "Elisa",
    "Fabrício",
    "Giovana",
    "Heitor",
    "Iara",
    "Joaquim",
    "Lavínia",
    "Matias",
    "Noemi",
    "Otávio",
    "Paloma",
    "Raul",
    "Sabrina",
    "Tadeu",
    "Valéria",
    "Yuri",
)
_LAST_NAMES = (
    "Albuquerque",
    "Bittencourt",
    "Cavalcante",
    "Drummond",
    "Esteves",
    "Figueira",
    "Guimarães",
    "Holanda",
    "Ibiapina",
    "Junqueira",
    "Lacerda",
    "Meireles",
    "Nogueira",
    "Quintela",
    "Rezende",
    "Sampaio",
    "Toledo",
    "Vasconcelos",
)
_START_TIMES = (
    "06:30",
    "07:00",
    "08:00",
    "09:30",
    "12:00",
    "15:00",
    "17:30",
    "18:30",
    "19:30",
    "20:30",
)


@dataclass(frozen=True, slots=True)
class _Tribe:
    instructors: frozenset[str]
    modalities: frozenset[str]
    period: DayPeriod


@dataclass(frozen=True, slots=True)
class _Persona:
    student: Student
    tribe: _Tribe | None
    period: DayPeriod
    weekly_sessions: int
    joined_week: int
    curiosity: float


def _name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _contraindications(spec: _ModalitySpec, intensity: int) -> frozenset[Restriction]:
    found: set[Restriction] = set()
    if intensity >= 4:
        found |= {Restriction.PREGNANCY, Restriction.HYPERTENSION}
        found.add(
            Restriction.LOWER_BACK_INJURY if spec.family == "pilates" else Restriction.KNEE_INJURY
        )
    if spec.id == "ashtanga":
        found.add(Restriction.LOWER_BACK_INJURY)
    return frozenset(found)


def _instructors(rng: random.Random, count: int) -> tuple[list[Instructor], dict[str, list[str]]]:
    instructors: list[Instructor] = []
    specialties: dict[str, list[str]] = {}
    used: set[str] = set()
    for index in range(count):
        name = _name(rng)
        while name in used:
            name = _name(rng)
        used.add(name)
        instructor_id = f"inst-{index + 1:02d}"
        instructors.append(Instructor(instructor_id, name))
        specialties[instructor_id] = [spec.id for spec in rng.sample(MODALITIES, k=2)]
    return instructors, specialties


def _lessons(
    rng: random.Random,
    count: int,
    instructors: list[Instructor],
    specialties: dict[str, list[str]],
) -> list[Lesson]:
    specs = {spec.id: spec for spec in MODALITIES}
    lessons: list[Lesson] = []
    for index in range(count):
        instructor = instructors[index % len(instructors)]
        spec = specs[rng.choice(specialties[instructor.id])]
        level = rng.choices(list(Level), weights=(2, 3, 3, 2))[0]
        intensity = max(1, min(5, spec.base_intensity + rng.choice((-1, 0, 0, 1))))
        focus = rng.sample(spec.focus, k=min(2, len(spec.focus)))
        phrases = [rng.choice(FOCUS_PHRASES[goal]) for goal in focus]
        capacity = 8 if spec.id == "pilates-aparelhos" else rng.choice((12, 15, 20))
        start_time = rng.choice(_START_TIMES)
        booked = capacity if rng.random() < 0.15 else rng.randint(0, capacity - 1)
        lessons.append(
            Lesson(
                id=f"aula-{index + 1:03d}",
                title=f"{spec.name} {level.label} · {start_time}",
                modality_id=spec.id,
                instructor_id=instructor.id,
                level=level,
                weekday=rng.randint(0, 5),
                start_time=start_time,
                duration_minutes=rng.choice((45, 60, 75)),
                intensity=intensity,
                capacity=capacity,
                booked_seats=booked,
                description=f"Foco em {' e '.join(phrases)}. {spec.style}",
                focus=frozenset(focus),
                contraindications=_contraindications(spec, intensity),
            )
        )
    return lessons


def _tribes(rng: random.Random, count: int, instructors: list[Instructor]) -> list[_Tribe]:
    return [
        _Tribe(
            instructors=frozenset(i.id for i in rng.sample(instructors, k=2)),
            modalities=frozenset(spec.id for spec in rng.sample(MODALITIES, k=2)),
            period=rng.choice(list(DayPeriod)),
        )
        for _ in range(count)
    ]


def _personas(rng: random.Random, config: GeneratorConfig, tribes: list[_Tribe]) -> list[_Persona]:
    specs = {spec.id: spec for spec in MODALITIES}
    personas: list[_Persona] = []
    for index in range(config.students):
        tribe = rng.choice(tribes) if rng.random() < 0.75 else None
        if tribe and rng.random() < 0.7:
            pool = sorted({goal for m in tribe.modalities for goal in specs[m].focus})
        else:
            pool = list(Goal)
        goals = tuple(rng.sample(pool, k=min(len(pool), rng.choice((1, 2, 2)))))
        restrictions = (
            frozenset({rng.choice(list(Restriction))}) if rng.random() < 0.2 else frozenset()
        )
        student = Student(
            id=f"aluno-{index + 1:04d}",
            name=_name(rng),
            level=rng.choices(
                (Level.BEGINNER, Level.INTERMEDIATE, Level.ADVANCED), weights=(4, 4, 2)
            )[0],
            goals=goals,
            restrictions=restrictions,
        )
        period = tribe.period if tribe and rng.random() < 0.8 else rng.choice(list(DayPeriod))
        personas.append(
            _Persona(
                student=student,
                tribe=tribe,
                period=period,
                weekly_sessions=rng.choice((1, 2, 2, 3)),
                joined_week=rng.randint(0, config.weeks // 2),
                curiosity=rng.uniform(0.2, 0.5),
            )
        )
    return personas


def _affinity(persona: _Persona, lesson: Lesson, noise: float) -> float:
    student = persona.student
    goal_match = len(set(student.goals) & lesson.focus) / len(student.goals)
    score = 2.0 * goal_match + 1.2 * (lesson.period is persona.period) + noise
    if persona.tribe:
        score += 1.8 * (lesson.instructor_id in persona.tribe.instructors)
        score += 1.0 * (lesson.modality_id in persona.tribe.modalities)
    return score


def _softmax_choice(rng: random.Random, items: list[Lesson], scores: list[float]) -> Lesson:
    temperature = 0.5
    peak = max(scores)
    weights = [math.exp((score - peak) / temperature) for score in scores]
    return rng.choices(items, weights=weights)[0]


def generate(config: GeneratorConfig | None = None) -> Dataset:
    """Gera o dataset completo. Mesma configuração (e seed) produz exatamente o mesmo resultado."""
    config = config or GeneratorConfig()
    rng = random.Random(config.seed)

    instructors, specialties = _instructors(rng, config.instructors)
    lessons = _lessons(rng, config.lessons, instructors, specialties)
    tribes = _tribes(rng, config.tribes, instructors)
    personas = _personas(rng, config, tribes)

    bookings: list[Booking] = []
    ratings: list[Rating] = []
    for persona in personas:
        student = persona.student
        eligible = [
            lesson
            for lesson in lessons
            if level_fits(student.level, lesson.level)
            and not (student.restrictions & lesson.contraindications)
        ]
        if not eligible:
            continue
        affinity = {lesson.id: _affinity(persona, lesson, rng.gauss(0, 0.4)) for lesson in eligible}

        known: list[Lesson] = []
        rated: set[str] = set()
        for week in range(persona.joined_week, config.weeks):
            unknown = [lesson for lesson in eligible if lesson not in known]
            if unknown and (len(known) < 2 or rng.random() < persona.curiosity):
                known.append(_softmax_choice(rng, unknown, [affinity[x.id] for x in unknown]))
            week_start = config.start + timedelta(weeks=week)
            for _ in range(persona.weekly_sessions):
                lesson = _softmax_choice(rng, known, [affinity[x.id] for x in known])
                hour, minute = (int(part) for part in lesson.start_time.split(":"))
                booked_at = week_start + timedelta(days=lesson.weekday, hours=hour, minutes=minute)
                bookings.append(Booking(student.id, lesson.id, booked_at))
                if lesson.id not in rated and rng.random() < 0.5:
                    rated.add(lesson.id)
                    raw = 1.0 + 0.9 * affinity[lesson.id] + rng.gauss(0, 0.6)
                    ratings.append(
                        Rating(
                            student.id,
                            lesson.id,
                            max(1, min(5, round(raw))),
                            booked_at + timedelta(hours=2),
                        )
                    )

    modalities = tuple(Modality(spec.id, spec.name, spec.family) for spec in MODALITIES)
    return Dataset(
        modalities=modalities,
        instructors=tuple(instructors),
        lessons=tuple(lessons),
        students=tuple(persona.student for persona in personas),
        bookings=tuple(sorted(bookings, key=lambda b: (b.booked_at, b.student_id, b.lesson_id))),
        ratings=tuple(sorted(ratings, key=lambda r: (r.rated_at, r.student_id, r.lesson_id))),
    )
