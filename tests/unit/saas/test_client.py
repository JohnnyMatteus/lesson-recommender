from collections.abc import Callable

import httpx
import pytest

from lesson_recommender.domain.errors import IntegrationError
from lesson_recommender.saas.client import (
    SaasApiClient,
    SaasIdentityClient,
    ServiceCredentials,
    ServiceTokenProvider,
)
from tests.unit.saas.saas_fakes import booking, session

BASE = "https://saas.example.com/api"


def make(handler: Callable[[httpx.Request], httpx.Response]) -> SaasApiClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    tokens = ServiceTokenProvider(
        http, ServiceCredentials("https://idp.example.com/token", "svc", "dev-only-secret")
    )
    return SaasApiClient(http, BASE, tokens)


def test_paginates_windows_and_uses_service_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "idp.example.com":
            assert b"grant_type=client_credentials" in request.content
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 300})
        seen.append(request)
        assert request.headers["authorization"] == "Bearer tok"
        item = session(
            f"s{len(seen)}", "ser", "Hatha Yoga", f"2026-11-{9 + len(seen):02d}T10:00:00Z"
        )
        return httpx.Response(200, json={"data": [item], "meta": {"last_page": 2}})

    from datetime import date

    sessions = make(handler).sessions(date(2026, 9, 1), date(2026, 11, 1))  # 62 dias
    # 62 dias = 2 janelas de 31 dias, cada uma com 2 páginas
    assert len(seen) == 4
    assert {r.url.params["from"] for r in seen} == {"2026-09-01", "2026-10-02"}
    assert len(sessions) == 4


def test_bookings_and_errors_are_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "idp.example.com":
            return httpx.Response(200, json={"access_token": "tok"})
        if request.url.path.endswith("/boom/bookings"):
            return httpx.Response(500)
        return httpx.Response(200, json={"data": [booking("b1", "s1", "m1")]})

    client = make(handler)
    assert client.bookings("s1")[0].member.id == "m1"
    with pytest.raises(IntegrationError):
        client.bookings("boom")


def test_token_failure_is_an_integration_error() -> None:
    client = make(lambda _r: httpx.Response(401))
    with pytest.raises(IntegrationError, match="token de serviço"):
        client.bookings("s1")


def test_identity_reads_member_id_with_the_students_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer aluno-token"
        return httpx.Response(200, json={"data": {"id": "m1", "role": "student"}})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert SaasIdentityClient(http, BASE).member_id("aluno-token") == "m1"
