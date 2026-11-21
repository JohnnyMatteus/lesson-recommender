"""Regras de negócio que decidem se uma aula pode ser recomendada a um aluno.

As regras são filtros duros: rodam antes do ranqueamento e nunca são compensadas por pontuação.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lesson_recommender.domain.models import Lesson, Level, Student


class Rejection(StrEnum):
    FULL = "lotada"
    LEVEL_MISMATCH = "fora_do_nivel"
    CONTRAINDICATED = "contraindicada"


@dataclass(frozen=True, slots=True)
class EligibilityPolicy:
    """Quais regras aplicar.

    A avaliação offline desliga a regra de lotação: a ocupação é uma fotografia do presente e
    não existia no momento das reservas históricas (ver docs/roteiros/avaliacao-offline.md).
    """

    enforce_capacity: bool = True
    enforce_level: bool = True
    enforce_restrictions: bool = True


def level_fits(student_level: Level, lesson_level: Level) -> bool:
    """Aula livre serve a todos; senão, o nível da aula é o do aluno ou um abaixo."""
    if lesson_level is Level.ALL:
        return True
    return 0 <= student_level - lesson_level <= 1


def rejection_reason(
    student: Student, lesson: Lesson, policy: EligibilityPolicy
) -> Rejection | None:
    if policy.enforce_restrictions and student.restrictions & lesson.contraindications:
        return Rejection.CONTRAINDICATED
    if policy.enforce_level and not level_fits(student.level, lesson.level):
        return Rejection.LEVEL_MISMATCH
    if policy.enforce_capacity and lesson.is_full:
        return Rejection.FULL
    return None


def is_eligible(student: Student, lesson: Lesson, policy: EligibilityPolicy) -> bool:
    return rejection_reason(student, lesson, policy) is None
