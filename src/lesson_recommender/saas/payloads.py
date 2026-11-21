"""Contrato do SaaS como ele chega pela API v1 (só o subconjunto que o recomendador usa).

Estes modelos ficam na borda: nada fora de `saas/` conhece nomes de campo do SaaS.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class SaasInstructor(_Payload):
    id: str
    name: str


class SaasSession(_Payload):
    id: str
    series_id: str | None = None
    title: str
    instructor: SaasInstructor
    starts_at: datetime
    ends_at: datetime
    starts_at_local: datetime
    capacity: int
    confirmed_count: int


class SaasMember(_Payload):
    id: str
    name: str


class SaasBooking(_Payload):
    id: str
    session_id: str
    member: SaasMember
    status: str
    queued_at: datetime
    confirmed_at: datetime | None = None


class SaasMe(_Payload):
    id: str
