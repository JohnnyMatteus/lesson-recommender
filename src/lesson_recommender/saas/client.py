"""Cliente da API v1 do SaaS com credencial de serviço (client credentials do Keycloak).

A credencial de serviço precisa de um token com a claim `tenant` do estúdio e papel de
administrador (a lista de reservas de uma sessão exige papel de equipe). Ver ADR 0009.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

from lesson_recommender.domain.errors import IntegrationError
from lesson_recommender.saas.payloads import SaasBooking, SaasMe, SaasSession

MAX_WINDOW_DAYS = 31  # limite da API de sessões por consulta
PER_PAGE = 100
TOKEN_SAFETY_SECONDS = 30


@dataclass(frozen=True, slots=True)
class ServiceCredentials:
    token_url: str
    client_id: str
    client_secret: str


class ServiceTokenProvider:
    """Obtém e reaproveita o access token de serviço até perto de expirar."""

    def __init__(self, http: httpx.Client, credentials: ServiceCredentials) -> None:
        self._http = http
        self._credentials = credentials
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token is None or time.monotonic() >= self._expires_at:
            try:
                response = self._http.post(
                    self._credentials.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._credentials.client_id,
                        "client_secret": self._credentials.client_secret,
                    },
                )
                response.raise_for_status()
                body = response.json()
                self._token = str(body["access_token"])
                ttl = float(body.get("expires_in", 60))
            except (httpx.HTTPError, KeyError, ValueError) as error:
                raise IntegrationError(
                    f"não foi possível obter o token de serviço: {error}"
                ) from error
            self._expires_at = time.monotonic() + max(ttl - TOKEN_SAFETY_SECONDS, 1.0)
        return self._token


class SaasApiClient:
    def __init__(self, http: httpx.Client, base_url: str, tokens: ServiceTokenProvider) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._tokens = tokens

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._http.get(
                f"{self._base}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self._tokens.token()}"},
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise IntegrationError(f"falha em GET {path}: {error}") from error
        if not isinstance(body, dict):
            raise IntegrationError(f"resposta fora do contrato em GET {path}")
        return body

    def _pages(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            body = self._get(path, {**params, "page": page, "per_page": PER_PAGE})
            yield from body.get("data", [])
            last = (body.get("meta") or {}).get("last_page", 1)
            if page >= int(last):
                return
            page += 1

    def sessions(self, start: date, end: date) -> list[SaasSession]:
        """Sessões entre as datas locais (inclusivas), em janelas que respeitam o limite da API."""
        found: dict[str, SaasSession] = {}
        cursor = start
        while cursor <= end:
            window_end = min(cursor + timedelta(days=MAX_WINDOW_DAYS - 1), end)
            params = {"from": cursor.isoformat(), "to": window_end.isoformat()}
            for item in self._pages("/v1/sessions", params):
                session = SaasSession.model_validate(item)
                found[session.id] = session
            cursor = window_end + timedelta(days=1)
        return sorted(found.values(), key=lambda s: (s.starts_at, s.id))

    def bookings(self, session_id: str) -> list[SaasBooking]:
        body = self._get(f"/v1/sessions/{session_id}/bookings")
        return [SaasBooking.model_validate(item) for item in body.get("data", [])]


class SaasIdentityClient:
    """Descobre o id do aluno no SaaS a partir do token do próprio aluno (`GET /v1/me`)."""

    def __init__(self, http: httpx.Client, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def member_id(self, access_token: str) -> str:
        try:
            response = self._http.get(
                f"{self._base}/v1/me", headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return SaasMe.model_validate(response.json()["data"]).id
        except (httpx.HTTPError, KeyError, ValueError) as error:
            raise IntegrationError(f"não foi possível resolver o aluno no SaaS: {error}") from error
