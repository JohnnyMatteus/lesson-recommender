"""Carga do dataset no Neo4j em lotes idempotentes (MERGE), com agregação das reservas."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, LiteralString

from neo4j import Driver, ManagedTransaction

from lesson_recommender.domain.models import Dataset
from lesson_recommender.graph import cypher

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadSummary:
    modalities: int
    instructors: int
    lessons: int
    students: int
    booking_edges: int
    rating_edges: int


def _chunks(rows: Sequence[dict[str, Any]], size: int) -> Iterator[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def booking_rows(dataset: Dataset) -> list[dict[str, Any]]:
    """Agrega reservas repetidas numa aresta por par aluno-aula (contagem e datas extremas)."""
    aggregated: dict[tuple[str, str], tuple[int, datetime, datetime]] = {}
    for booking in dataset.bookings:
        key = (booking.student_id, booking.lesson_id)
        if key in aggregated:
            count, first, last = aggregated[key]
            aggregated[key] = (
                count + 1,
                min(first, booking.booked_at),
                max(last, booking.booked_at),
            )
        else:
            aggregated[key] = (1, booking.booked_at, booking.booked_at)
    return [
        {
            "student_id": student,
            "lesson_id": lesson,
            "count": count,
            "first_at": first.isoformat(),
            "last_at": last.isoformat(),
        }
        for (student, lesson), (count, first, last) in sorted(aggregated.items())
    ]


def rating_rows(dataset: Dataset) -> list[dict[str, Any]]:
    """Mantém só a nota mais recente de cada par aluno-aula."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for rating in sorted(dataset.ratings, key=lambda r: r.rated_at):
        latest[(rating.student_id, rating.lesson_id)] = {
            "student_id": rating.student_id,
            "lesson_id": rating.lesson_id,
            "score": rating.score,
            "at": rating.rated_at.isoformat(),
        }
    return [latest[key] for key in sorted(latest)]


def _run_batch(tx: ManagedTransaction, query: LiteralString, rows: list[dict[str, Any]]) -> None:
    tx.run(query, rows=rows).consume()


class GraphLoader:
    def __init__(self, driver: Driver, *, database: str | None = None, batch_size: int = 1000):
        self._driver = driver
        self._database = database
        self._batch_size = batch_size

    def load(self, dataset: Dataset, *, replace: bool = True) -> LoadSummary:
        bookings = booking_rows(dataset)
        ratings = rating_rows(dataset)
        with self._driver.session(database=self._database) as session:
            for statement in cypher.CONSTRAINTS:
                session.run(statement).consume()
            if replace:
                session.run(cypher.CLEAR_GRAPH).consume()
        self._write(
            cypher.MERGE_MODALITIES,
            [{"id": m.id, "name": m.name, "family": m.family} for m in dataset.modalities],
        )
        self._write(
            cypher.MERGE_INSTRUCTORS, [{"id": i.id, "name": i.name} for i in dataset.instructors]
        )
        self._write(
            cypher.MERGE_LESSONS,
            [
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "modality_id": lesson.modality_id,
                    "instructor_id": lesson.instructor_id,
                    "level": lesson.level.name,
                    "weekday": lesson.weekday,
                    "start_time": lesson.start_time,
                    "duration_minutes": lesson.duration_minutes,
                    "intensity": lesson.intensity,
                    "capacity": lesson.capacity,
                    "booked_seats": lesson.booked_seats,
                    "description": lesson.description,
                    "focus": sorted(goal.value for goal in lesson.focus),
                    "contraindications": sorted(r.value for r in lesson.contraindications),
                }
                for lesson in dataset.lessons
            ],
        )
        self._write(
            cypher.MERGE_STUDENTS,
            [
                {
                    "id": s.id,
                    "name": s.name,
                    "level": s.level.name,
                    "goals": [goal.value for goal in s.goals],
                    "restrictions": sorted(r.value for r in s.restrictions),
                }
                for s in dataset.students
            ],
        )
        self._write(cypher.MERGE_BOOKINGS, bookings)
        self._write(cypher.MERGE_RATINGS, ratings)
        summary = LoadSummary(
            modalities=len(dataset.modalities),
            instructors=len(dataset.instructors),
            lessons=len(dataset.lessons),
            students=len(dataset.students),
            booking_edges=len(bookings),
            rating_edges=len(ratings),
        )
        logger.info("grafo carregado", extra=asdict(summary))
        return summary

    def _write(self, query: LiteralString, rows: Sequence[dict[str, Any]]) -> None:
        with self._driver.session(database=self._database) as session:
            for chunk in _chunks(rows, self._batch_size):
                session.execute_write(_run_batch, query, list(chunk))
