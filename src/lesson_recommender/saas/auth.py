"""Validação do access token RS256 do Keycloak do SaaS (mesmas regras da API do SaaS)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

from lesson_recommender.domain.errors import AuthenticationError

ALGORITHMS = ["RS256"]  # lista fixa: bloqueia `none` e a confusão RS256/HS256


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    tenant: str
    token: str


class TokenVerifier:
    def __init__(
        self,
        signing_key: Callable[[str], Any],
        *,
        issuer: str,
        audience: str,
        leeway_seconds: int = 30,
    ) -> None:
        self._signing_key = signing_key
        self._issuer = issuer
        self._audience = audience
        self._leeway = leeway_seconds

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._signing_key(token),
                algorithms=ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            raise AuthenticationError(f"token inválido: {error}") from error
        tenant = claims.get("tenant")
        if not isinstance(tenant, str) or not tenant:
            raise AuthenticationError("token sem a claim 'tenant'")
        return Principal(subject=str(claims["sub"]), tenant=tenant, token=token)


def jwks_signing_key(jwks_url: str) -> Callable[[str], Any]:
    """Chaves vindas do JWKS do Keycloak, em cache (rotação por `kid` novo)."""
    client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=600, timeout=5)

    def resolve(token: str) -> Any:
        try:
            return client.get_signing_key_from_jwt(token).key
        except jwt.PyJWTError as error:
            raise AuthenticationError(f"chave de assinatura indisponível: {error}") from error

    return resolve


def static_signing_key(public_key_pem: str) -> Callable[[str], Any]:
    return lambda _token: public_key_pem
