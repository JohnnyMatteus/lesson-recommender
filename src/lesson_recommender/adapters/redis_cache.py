"""Adaptador Redis da porta `RecommendationCache`.

Layout: um hash por aluno (`lr:recs:{student_id}`), um campo por `k`. Invalidar o aluno é um
único DEL, sem SCAN. O TTL é gravado com `EXPIRE ... NX` na primeira escrita do hash: novas
escritas não o estendem, então nenhuma entrada vive mais que o TTL.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from opentelemetry import trace
from redis import Redis, RedisError

from lesson_recommender.domain.models import Goal, Lesson, Level, Restriction
from lesson_recommender.observability import CACHE_REQUESTS
from lesson_recommender.recommender.hybrid import Recommendation, ScoreBreakdown

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

KEY_PREFIX = "lr:recs:"


def cache_key(student_id: str) -> str:
    return f"{KEY_PREFIX}{student_id}"


def _lesson_to_dict(lesson: Lesson) -> dict[str, Any]:
    return {
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


def _lesson_from_dict(data: dict[str, Any]) -> Lesson:
    return Lesson(
        **{
            **data,
            "level": Level[data["level"]],
            "focus": frozenset(Goal(goal) for goal in data["focus"]),
            "contraindications": frozenset(Restriction(r) for r in data["contraindications"]),
        }
    )


def encode(items: list[Recommendation]) -> str:
    return json.dumps(
        [
            {
                "lesson": _lesson_to_dict(item.lesson),
                "score": item.score,
                "breakdown": {
                    "content": item.breakdown.content,
                    "collaborative": item.breakdown.collaborative,
                    "popularity": item.breakdown.popularity,
                },
                "reasons": list(item.reasons),
            }
            for item in items
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode(raw: str | bytes) -> list[Recommendation]:
    return [
        Recommendation(
            lesson=_lesson_from_dict(item["lesson"]),
            score=item["score"],
            breakdown=ScoreBreakdown(**item["breakdown"]),
            reasons=tuple(item["reasons"]),
        )
        for item in json.loads(raw)
    ]


class RedisRecommendationCache:
    """Degrada para 'sem cache' se o Redis falhar: registra, conta e segue sem ele."""

    def __init__(self, client: Redis, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds deve ser positivo: {ttl_seconds}")
        self._client = client
        self._ttl = ttl_seconds

    def get(self, student_id: str, k: int) -> list[Recommendation] | None:
        with tracer.start_as_current_span("cache.get") as span:
            try:
                raw = self._client.hget(cache_key(student_id), str(k))
            except RedisError as error:
                self._fail("get", student_id, error)
                return None
            hit = raw is not None
            span.set_attribute("cache.hit", hit)
            CACHE_REQUESTS.labels("hit" if hit else "miss").inc()
            return decode(raw) if raw is not None else None

    def put(self, student_id: str, k: int, items: list[Recommendation]) -> None:
        key = cache_key(student_id)
        try:
            pipe = self._client.pipeline(transaction=True)
            pipe.hset(key, str(k), encode(items))
            pipe.expire(key, self._ttl, nx=True)
            pipe.execute()
        except RedisError as error:
            self._fail("put", student_id, error)

    def invalidate(self, student_id: str) -> None:
        try:
            self._client.delete(cache_key(student_id))
        except RedisError as error:
            self._fail("invalidate", student_id, error)

    def _fail(self, operation: str, student_id: str, error: RedisError) -> None:
        CACHE_REQUESTS.labels("error").inc()
        logger.warning(
            "cache indisponível",
            extra={"operation": operation, "student_id": student_id, "error": str(error)},
        )
