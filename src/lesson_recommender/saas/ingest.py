"""Ingestão: lê sessões e reservas de um estúdio pela API v1 e entrega o `Dataset` traduzido."""

from __future__ import annotations

from datetime import datetime, timedelta

from lesson_recommender.domain.models import Dataset
from lesson_recommender.saas.acl import translate
from lesson_recommender.saas.client import SaasApiClient


def ingest_tenant(
    client: SaasApiClient, *, now: datetime, lookback_days: int, lookahead_days: int
) -> Dataset:
    """Janela de histórico (passado) + próximas turmas (para a ocupação atual)."""
    start = (now - timedelta(days=lookback_days)).date()
    end = (now + timedelta(days=lookahead_days)).date()
    sessions = client.sessions(start, end)
    bookings = [booking for session in sessions for booking in client.bookings(session.id)]
    return translate(sessions, bookings, now=now)
