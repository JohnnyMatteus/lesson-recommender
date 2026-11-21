"""Adaptador Neo4j: implementa as portas de catálogo e de colaborativo com Cypher."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, LiteralString

from neo4j import Driver

from lesson_recommender.domain.models import (
    CollaborativeSignal,
    Goal,
    Instructor,
    Lesson,
    Level,
    Modality,
    Restriction,
    Student,
    StudentHistory,
)
from lesson_recommender.graph import cypher
from lesson_recommender.recommender.collaborative import UNRATED_WEIGHT


def _lesson_from_record(data: Mapping[str, Any]) -> Lesson:
    return Lesson(
        id=data["id"],
        title=data["title"],
        modality_id=data["modality_id"],
        instructor_id=data["instructor_id"],
        level=Level[data["level"]],
        weekday=data["weekday"],
        start_time=data["start_time"],
        duration_minutes=data["duration_minutes"],
        intensity=data["intensity"],
        capacity=data["capacity"],
        booked_seats=data["booked_seats"],
        description=data["description"],
        focus=frozenset(Goal(goal) for goal in data["focus"]),
        contraindications=frozenset(Restriction(r) for r in data["contraindications"]),
    )


class Neo4jRepository:
    """Catálogo, modalidades e instrutores ficam em cache após a primeira leitura.

    O catálogo muda pouco (grade do estúdio); histórico e colaborativo são sempre consultados.
    Uma reserva muda a ocupação, então descarta o catálogo em memória.
    """

    def __init__(self, driver: Driver, *, database: str | None = None) -> None:
        self._driver = driver
        self._database = database
        self._lessons: tuple[Lesson, ...] | None = None
        self._modalities: dict[str, Modality] | None = None
        self._instructors: dict[str, Instructor] | None = None

    def _query(self, query: LiteralString, **parameters: Any) -> list[dict[str, Any]]:
        records, _, _ = self._driver.execute_query(
            query, parameters_=parameters, database_=self._database
        )
        return [record.data() for record in records]

    def get_student(self, student_id: str) -> Student | None:
        rows = self._query(cypher.GET_STUDENT, student_id=student_id)
        if not rows:
            return None
        row = rows[0]
        return Student(
            id=row["id"],
            name=row["name"],
            level=Level[row["level"]],
            goals=tuple(Goal(goal) for goal in row["goals"]),
            restrictions=frozenset(Restriction(r) for r in row["restrictions"]),
        )

    def list_lessons(self) -> Sequence[Lesson]:
        if self._lessons is None:
            rows = self._query(cypher.LIST_LESSONS)
            self._lessons = tuple(_lesson_from_record(row["lesson"]) for row in rows)
        return self._lessons

    def modalities(self) -> Mapping[str, Modality]:
        if self._modalities is None:
            self._modalities = {
                row["id"]: Modality(row["id"], row["name"], row["family"])
                for row in self._query(cypher.LIST_MODALITIES)
            }
        return self._modalities

    def instructors(self) -> Mapping[str, Instructor]:
        if self._instructors is None:
            self._instructors = {
                row["id"]: Instructor(row["id"], row["name"])
                for row in self._query(cypher.LIST_INSTRUCTORS)
            }
        return self._instructors

    def history(self, student_id: str) -> StudentHistory:
        rows = self._query(cypher.STUDENT_HISTORY, student_id=student_id)
        return StudentHistory(
            bookings={row["lesson_id"]: row["count"] for row in rows},
            ratings={row["lesson_id"]: row["score"] for row in rows if row["score"] is not None},
        )

    def record_booking(self, student_id: str, lesson_id: str, booked_at: datetime) -> bool:
        rows = self._query(
            cypher.RECORD_BOOKING,
            student_id=student_id,
            lesson_id=lesson_id,
            booked_at=booked_at.isoformat(),
        )
        self._lessons = None
        return bool(rows)

    def popularity(self) -> Mapping[str, int]:
        return {row["lesson_id"]: row["students"] for row in self._query(cypher.POPULARITY)}

    def neighbor_scores(
        self, student_id: str, *, neighbors: int
    ) -> Mapping[str, CollaborativeSignal]:
        if neighbors <= 0:
            raise ValueError(f"neighbors deve ser positivo: {neighbors}")
        rows = self._query(
            cypher.COLLABORATIVE_NEIGHBORHOOD,
            student_id=student_id,
            neighbors=neighbors,
            unrated_weight=UNRATED_WEIGHT,
        )
        return {
            row["lesson_id"]: CollaborativeSignal(score=row["score"], support=row["support"])
            for row in rows
        }
