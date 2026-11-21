from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.api.app import create_app
from lesson_recommender.api.tenant_routes import build_tenant_router
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender
from lesson_recommender.saas.auth import Principal, TokenVerifier, static_signing_key
from lesson_recommender.saas.tenants import TenantRecommenders
from tests.factories import studio

ISSUER = "http://idp.example.com/realms/estudios"
FRONT = "http://localhost:5173"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem_public(key: rsa.RSAPrivateKey) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


def token(
    *,
    tenant: str | None = "lotus",
    sub: str = "kc-ana",
    key: rsa.RSAPrivateKey = _KEY,
    audience: str = "studio-api",
    expires_in: int = 300,
    algorithm: str = "RS256",
) -> str:
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": audience,
        "sub": sub,
        "exp": int(time.time()) + expires_in,
    }
    if tenant is not None:
        claims["tenant"] = tenant
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "k1"})


class FakeIdentity:
    """sub do Keycloak -> id do aluno no SaaS (o mesmo que o `/v1/me` devolveria)."""

    def member_id(self, principal: Principal) -> str:
        return {"kc-ana": "ana", "kc-bia": "bia"}[principal.subject]


def recommender_for(dataset_factory: Callable[[], Any]) -> Any:
    def factory(dataset: Any) -> HybridRecommender:
        repo = InMemoryRepository(dataset)
        content = ContentModel(
            HashingEmbedder(128), repo.list_lessons(), repo.modalities(), repo.instructors()
        )
        return HybridRecommender(repo, repo, content, neighbors=10)

    return factory


@pytest.fixture
def client() -> TestClient:
    tenants = TenantRecommenders(recommender_for(studio))
    tenants.replace("lotus", studio())
    tenants.replace("equilibrio", studio())
    verifier = TokenVerifier(
        static_signing_key(_pem_public(_KEY)), issuer=ISSUER, audience="studio-api"
    )
    router = build_tenant_router(verifier, FakeIdentity(), tenants)
    return TestClient(create_app(tenant_router=router, cors_origins=[FRONT]))


def get(client: TestClient, tenant: str, student: str, bearer: str | None, **params: object) -> Any:
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    return client.get(
        f"/tenants/{tenant}/students/{student}/recommendations", headers=headers, params=params
    )


def test_student_gets_own_recommendations(client: TestClient) -> None:
    response = get(client, "lotus", "ana", token(), k=3)
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == "ana"
    assert body["items"][0]["lesson"]["id"] == "y2"


def test_student_cannot_read_someone_elses(client: TestClient) -> None:
    response = get(client, "lotus", "bia", token())
    assert response.status_code == 403


def test_token_from_another_tenant_is_forbidden(client: TestClient) -> None:
    assert get(client, "equilibrio", "ana", token(tenant="lotus")).status_code == 403


def test_unknown_tenant_with_matching_claim_is_404(client: TestClient) -> None:
    assert get(client, "fantasma", "ana", token(tenant="fantasma")).status_code == 404


@pytest.mark.parametrize(
    "bearer",
    [
        None,
        "lixo",
        token(expires_in=-600),
        token(audience="outra-api"),
        token(key=_OTHER_KEY),
        token(tenant=None),
    ],
    ids=["ausente", "malformado", "expirado", "audiência", "assinatura", "sem-tenant"],
)
def test_invalid_tokens_are_401(client: TestClient, bearer: str | None) -> None:
    response = get(client, "lotus", "ana", bearer)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "não autenticado"}


def test_hs256_token_signed_with_the_public_key_is_rejected(client: TestClient) -> None:
    forged = jwt.encode(
        {
            "iss": ISSUER,
            "aud": "studio-api",
            "sub": "kc-ana",
            "tenant": "lotus",
            "exp": int(time.time()) + 60,
        },
        "segredo",
        algorithm="HS256",
    )
    assert get(client, "lotus", "ana", forged).status_code == 401


def test_k_is_validated(client: TestClient) -> None:
    assert get(client, "lotus", "ana", token(), k=0).status_code == 422


def test_cors_allows_the_saas_front_only(client: TestClient) -> None:
    path = "/tenants/lotus/students/ana/recommendations"
    preflight = client.options(
        path,
        headers={
            "Origin": FRONT,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == FRONT
    assert "authorization" in preflight.headers["access-control-allow-headers"].lower()
    denied = client.options(
        path,
        headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_demo_route_is_absent_in_saas_mode(client: TestClient) -> None:
    assert client.get("/students/ana/recommendations").status_code == 404
