"""Payloads no formato da API v1 do SaaS, para os testes da integração."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def session(
    session_id: str,
    series_id: str | None,
    title: str,
    starts_at: str,
    *,
    local: str | None = None,
    confirmed: int = 2,
    capacity: int = 10,
    instructor: str = "inst-1",
) -> dict[str, Any]:
    return {
        "id": session_id,
        "series_id": series_id,
        "title": title,
        "instructor": {"id": instructor, "name": "Instrutora Exemplo"},
        "starts_at": starts_at,
        "ends_at": starts_at.replace("T10", "T11"),
        "starts_at_local": local or starts_at.replace("Z", "-03:00").replace("T10", "T07"),
        "timezone": "America/Sao_Paulo",
        "capacity": capacity,
        "confirmed_count": confirmed,
        "available_spots": capacity - confirmed,
        "waitlist_count": 0,
    }


def booking(
    booking_id: str, session_id: str, member: str, status: str = "confirmed"
) -> dict[str, Any]:
    return {
        "id": booking_id,
        "session_id": session_id,
        "member": {"id": member, "name": f"Aluna {member}"},
        "status": status,
        "queued_at": "2026-11-10T09:00:00.000000Z",
        "confirmed_at": "2026-11-10T09:00:01Z" if status == "confirmed" else None,
        "canceled_at": None,
    }
