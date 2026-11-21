"""Contrato HTTP da API (separado das entidades de domínio)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from lesson_recommender.recommender.hybrid import Recommendation


class ScoreBreakdownOut(BaseModel):
    content: float = Field(description="Similaridade de conteúdo normalizada (0 a 1)")
    collaborative: float = Field(description="Sinal de alunos parecidos normalizado (0 a 1)")
    popularity: float = Field(description="Popularidade relativa (0 a 1)")


class LessonOut(BaseModel):
    id: str
    title: str
    modality_id: str
    instructor_id: str
    level: str
    schedule: str
    intensity: int
    seats_left: int


class RecommendationOut(BaseModel):
    lesson: LessonOut
    score: float
    breakdown: ScoreBreakdownOut
    reasons: list[str] = Field(description="Por que esta aula foi recomendada")

    @staticmethod
    def from_domain(item: Recommendation) -> RecommendationOut:
        lesson = item.lesson
        return RecommendationOut(
            lesson=LessonOut(
                id=lesson.id,
                title=lesson.title,
                modality_id=lesson.modality_id,
                instructor_id=lesson.instructor_id,
                level=lesson.level.label,
                schedule=lesson.schedule_label,
                intensity=lesson.intensity,
                seats_left=lesson.capacity - lesson.booked_seats,
            ),
            score=item.score,
            breakdown=ScoreBreakdownOut(
                content=item.breakdown.content,
                collaborative=item.breakdown.collaborative,
                popularity=item.breakdown.popularity,
            ),
            reasons=list(item.reasons),
        )


class RecommendationsResponse(BaseModel):
    student_id: str
    k: int
    weights: dict[str, float]
    items: list[RecommendationOut]


class ErrorResponse(BaseModel):
    detail: str
