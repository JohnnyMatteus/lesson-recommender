from __future__ import annotations

import httpx
import pytest

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.domain.errors import StudentNotFoundError
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender
from lesson_recommender.saas.client import SaasApiClient, ServiceCredentials, ServiceTokenProvider
from lesson_recommender.saas.sync import TenantSyncer
from lesson_recommender.saas.tenants import TenantRecommenders
from tests.unit.saas.saas_fakes import NOW, booking, session


def _factory(dataset: object) -> HybridRecommender:
    repo = InMemoryRepository(dataset)  # type: ignore[arg-type]
    content = ContentModel(
        HashingEmbedder(64), repo.list_lessons(), repo.modalities(), repo.instructors()
    )
    return HybridRecommender(repo, repo, content, neighbors=5)


def _client(
    sessions: list[dict[str, object]], bookings: dict[str, list[dict[str, object]]]
) -> SaasApiClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "idp.example.com":
            return httpx.Response(200, json={"access_token": "t"})
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"data": sessions, "meta": {"last_page": 1}})
        session_id = request.url.path.split("/")[3]
        return httpx.Response(200, json={"data": bookings.get(session_id, [])})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    tokens = ServiceTokenProvider(http, ServiceCredentials("https://idp.example.com/t", "c", "s"))
    return SaasApiClient(http, "https://saas.example.com", tokens)


def test_tenants_never_share_students_lessons_or_neighbors() -> None:
    lotus = _client(
        [
            session("s1", "a", "Hatha Yoga", "2026-11-10T10:00:00Z"),
            session("s2", "b", "Yin Yoga", "2026-11-11T10:00:00Z"),
        ],
        {"s1": [booking("b1", "s1", "m-lotus")], "s2": [booking("b2", "s2", "m-lotus")]},
    )
    equilibrio = _client(
        [session("s9", "z", "Pilates Solo", "2026-11-10T10:00:00Z")],
        {"s9": [booking("b9", "s9", "m-eq")]},
    )
    tenants = TenantRecommenders(_factory)
    syncer = TenantSyncer(
        {"lotus": lotus, "equilibrio": equilibrio},
        tenants,
        lookback_days=30,
        lookahead_days=7,
        clock=lambda: NOW,
    )
    assert syncer.sync_all() == {"lotus": True, "equilibrio": True}

    lotus_rec, eq_rec = tenants.get("lotus"), tenants.get("equilibrio")
    assert lotus_rec is not None
    assert eq_rec is not None
    assert lotus_rec.recommend("m-lotus", 5) is not None
    with pytest.raises(StudentNotFoundError):
        lotus_rec.recommend("m-eq", 5)
    with pytest.raises(StudentNotFoundError):
        eq_rec.recommend("m-lotus", 5)
    assert tenants.get("outro") is None


def test_failed_sync_keeps_previous_snapshot_and_other_tenants() -> None:
    good = _client(
        [session("s1", "a", "Hatha Yoga", "2026-11-10T10:00:00Z")],
        {"s1": [booking("b1", "s1", "m1")]},
    )
    broken = SaasApiClient(
        httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(500))),
        "https://saas.example.com",
        ServiceTokenProvider(
            httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(500))),
            ServiceCredentials("https://idp.example.com/t", "c", "s"),
        ),
    )
    tenants = TenantRecommenders(_factory)
    syncer = TenantSyncer(
        {"ok": good, "quebrado": broken},
        tenants,
        lookback_days=30,
        lookahead_days=7,
        clock=lambda: NOW,
    )
    assert syncer.sync_all() == {"ok": True, "quebrado": False}
    assert tenants.get("ok") is not None
    assert tenants.get("quebrado") is None
