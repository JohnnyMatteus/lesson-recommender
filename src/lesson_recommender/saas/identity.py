"""Quem é o aluno no SaaS: ponte entre o `sub` do Keycloak e o id usado nas reservas."""

from __future__ import annotations

import time
from typing import Protocol

from lesson_recommender.saas.auth import Principal


class IdentityResolver(Protocol):
    def member_id(self, principal: Principal) -> str: ...


class MemberIdSource(Protocol):
    def member_id(self, access_token: str) -> str: ...


class CachedIdentityResolver:
    """Resolve pelo `/v1/me` com o token do próprio aluno e guarda por (tenant, sub)."""

    def __init__(self, source: MemberIdSource, *, ttl_seconds: float = 900.0) -> None:
        self._source = source
        self._ttl = ttl_seconds
        self._cache: dict[tuple[str, str], tuple[str, float]] = {}

    def member_id(self, principal: Principal) -> str:
        key = (principal.tenant, principal.subject)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached is not None and cached[1] > now:
            return cached[0]
        member = self._source.member_id(principal.token)
        self._cache[key] = (member, now + self._ttl)
        return member
