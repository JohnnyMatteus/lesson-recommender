"""Split temporal: treina com o passado e testa nas descobertas do futuro.

O corte é um instante global (quantil das datas de reserva), não um corte por aluno: assim o
modelo nunca vê nenhuma interação posterior ao corte, de nenhum aluno (sem vazamento).

Relevantes de teste de um aluno = aulas que ele reservou pela primeira vez depois do corte.
Reservas repetidas de aulas já conhecidas não contam: o produto quer ajudar a descobrir aulas.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from lesson_recommender.domain.models import Dataset


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    cutoff: datetime
    train: Dataset
    relevant: dict[str, frozenset[str]]
    test_bookings: int


def temporal_split(dataset: Dataset, *, test_fraction: float = 0.2) -> TemporalSplit:
    if not 0.0 < test_fraction < 1.0:
        raise ValueError(f"test_fraction deve estar em (0, 1): {test_fraction}")
    if not dataset.bookings:
        raise ValueError("dataset sem reservas não pode ser dividido")

    ordered = sorted(dataset.bookings, key=lambda booking: booking.booked_at)
    cutoff = ordered[int(len(ordered) * (1.0 - test_fraction))].booked_at
    train_bookings = tuple(b for b in ordered if b.booked_at < cutoff)
    test_bookings = [b for b in ordered if b.booked_at >= cutoff]

    seen: dict[str, set[str]] = {}
    for booking in train_bookings:
        seen.setdefault(booking.student_id, set()).add(booking.lesson_id)

    relevant: dict[str, set[str]] = {}
    for booking in test_bookings:
        history = seen.get(booking.student_id)
        # Alunos sem histórico de treino ficam de fora: são cold start, avaliados à parte.
        if history and booking.lesson_id not in history:
            relevant.setdefault(booking.student_id, set()).add(booking.lesson_id)

    train = replace(
        dataset,
        bookings=train_bookings,
        ratings=tuple(r for r in dataset.ratings if r.rated_at < cutoff),
    )
    return TemporalSplit(
        cutoff=cutoff,
        train=train,
        relevant={student: frozenset(items) for student, items in relevant.items()},
        test_bookings=len(test_bookings),
    )
