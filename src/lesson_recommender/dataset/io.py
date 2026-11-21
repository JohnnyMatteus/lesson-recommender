"""Serialização do dataset em JSON (um arquivo, ordenado e estável para diffs)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
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

SCHEMA_VERSION = 1


def dataset_to_dict(dataset: Dataset) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "modalities": [
            {"id": m.id, "name": m.name, "family": m.family} for m in dataset.modalities
        ],
        "instructors": [{"id": i.id, "name": i.name} for i in dataset.instructors],
        "lessons": [
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
        "students": [
            {
                "id": s.id,
                "name": s.name,
                "level": s.level.name,
                "goals": [goal.value for goal in s.goals],
                "restrictions": sorted(r.value for r in s.restrictions),
            }
            for s in dataset.students
        ],
        "bookings": [
            {"student_id": b.student_id, "lesson_id": b.lesson_id, "at": b.booked_at.isoformat()}
            for b in dataset.bookings
        ],
        "ratings": [
            {
                "student_id": r.student_id,
                "lesson_id": r.lesson_id,
                "score": r.score,
                "at": r.rated_at.isoformat(),
            }
            for r in dataset.ratings
        ],
    }


def dataset_from_dict(data: dict[str, Any]) -> Dataset:
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"versão de schema não suportada: {version!r}")
    return Dataset(
        modalities=tuple(Modality(**m) for m in data["modalities"]),
        instructors=tuple(Instructor(**i) for i in data["instructors"]),
        lessons=tuple(
            Lesson(
                id=item["id"],
                title=item["title"],
                modality_id=item["modality_id"],
                instructor_id=item["instructor_id"],
                level=Level[item["level"]],
                weekday=item["weekday"],
                start_time=item["start_time"],
                duration_minutes=item["duration_minutes"],
                intensity=item["intensity"],
                capacity=item["capacity"],
                booked_seats=item["booked_seats"],
                description=item["description"],
                focus=frozenset(Goal(goal) for goal in item["focus"]),
                contraindications=frozenset(Restriction(r) for r in item["contraindications"]),
            )
            for item in data["lessons"]
        ),
        students=tuple(
            Student(
                id=item["id"],
                name=item["name"],
                level=Level[item["level"]],
                goals=tuple(Goal(goal) for goal in item["goals"]),
                restrictions=frozenset(Restriction(r) for r in item["restrictions"]),
            )
            for item in data["students"]
        ),
        bookings=tuple(
            Booking(b["student_id"], b["lesson_id"], datetime.fromisoformat(b["at"]))
            for b in data["bookings"]
        ),
        ratings=tuple(
            Rating(r["student_id"], r["lesson_id"], r["score"], datetime.fromisoformat(r["at"]))
            for r in data["ratings"]
        ),
    )


def save_dataset(dataset: Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset_to_dict(dataset), ensure_ascii=False, indent=1) + "\n")


def load_dataset(path: Path) -> Dataset:
    if not path.exists():
        raise FileNotFoundError(
            f"dataset não encontrado em {path}; gere com: lesson-recommender generate"
        )
    return dataset_from_dict(json.loads(path.read_text()))
