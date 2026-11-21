"""Explicações em linguagem natural para cada recomendação.

As frases são derivadas dos mesmos sinais que geram a pontuação, nunca inventadas depois:
se o colaborativo não contribuiu, a explicação não fala de "alunos parecidos".
"""

from __future__ import annotations

from dataclasses import dataclass

from lesson_recommender.domain.models import CollaborativeSignal, Lesson, Student

SIMILAR_LESSON_THRESHOLD = 0.3
POPULAR_THRESHOLD = 0.7


@dataclass(frozen=True, slots=True)
class ExplanationInput:
    student: Student
    lesson: Lesson
    content_active: bool
    similar_lesson_title: str | None
    similar_lesson_score: float
    collaborative: CollaborativeSignal | None
    popularity_share: float


def _join(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " e " + labels[-1]


def explain(data: ExplanationInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if data.content_active:
        matched = [goal.label for goal in data.student.goals if goal in data.lesson.focus]
        if matched:
            reasons.append(f"Trabalha seus objetivos: {_join(matched)}.")
        if data.similar_lesson_title and data.similar_lesson_score >= SIMILAR_LESSON_THRESHOLD:
            reasons.append(f"Parecida com '{data.similar_lesson_title}', que você já frequenta.")
    if data.collaborative and data.collaborative.support > 0:
        count = data.collaborative.support
        noun = "aluno" if count == 1 else "alunos"
        reasons.append(f"Reservada por {count} {noun} com histórico parecido com o seu.")
    if data.popularity_share >= POPULAR_THRESHOLD:
        reasons.append("Está entre as aulas mais procuradas do estúdio.")
    reasons.append(
        f"Nível {data.lesson.level.label} compatível com o seu ({data.student.level.label}); "
        f"{data.lesson.schedule_label}."
    )
    return tuple(reasons)
