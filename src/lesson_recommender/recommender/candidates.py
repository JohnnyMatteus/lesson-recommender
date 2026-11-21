"""Seleção de candidatas compartilhada pelo modelo híbrido e pelos baselines.

Todos os modelos competem no mesmo conjunto: aulas que o aluno ainda não reservou e que passam
nas regras de negócio. Sem isso, a comparação com baselines seria injusta.
"""

from __future__ import annotations

from collections.abc import Sequence

from lesson_recommender.domain.models import Lesson, Student, StudentHistory
from lesson_recommender.domain.rules import EligibilityPolicy, is_eligible


def eligible_candidates(
    student: Student,
    lessons: Sequence[Lesson],
    history: StudentHistory,
    policy: EligibilityPolicy,
) -> list[Lesson]:
    booked = history.booked_lesson_ids
    return [
        lesson
        for lesson in lessons
        if lesson.id not in booked and is_eligible(student, lesson, policy)
    ]
