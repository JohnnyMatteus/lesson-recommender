"""Rota autenticada por tenant: `GET /tenants/{tenant}/students/{id}/recommendations`.

Ordem das checagens (cada uma falha fechada):
1. token válido (RS256, emissor, audiência, expiração) -> 401;
2. tenant do caminho igual à claim `tenant` do token -> 403;
3. estúdio atendido por este serviço -> 404;
4. o aluno do caminho é o dono do token (id resolvido no SaaS) -> 403.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lesson_recommender.api.render import build_response
from lesson_recommender.api.schemas import ErrorResponse, RecommendationsResponse
from lesson_recommender.domain.errors import (
    AuthenticationError,
    ForbiddenError,
    StudentNotFoundError,
)
from lesson_recommender.recommender.hybrid import MAX_K
from lesson_recommender.saas.auth import Principal, TokenVerifier
from lesson_recommender.saas.identity import IdentityResolver
from lesson_recommender.saas.tenants import TenantRecommenders

_bearer = HTTPBearer(auto_error=False)


def build_tenant_router(
    verifier: TokenVerifier, identity: IdentityResolver, tenants: TenantRecommenders
) -> APIRouter:
    router = APIRouter(tags=["recomendações por estúdio"])

    def principal(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> Principal:
        if credentials is None:
            raise AuthenticationError("token ausente")
        return verifier.verify(credentials.credentials)

    @router.get(
        "/tenants/{tenant}/students/{student_id}/recommendations",
        response_model=RecommendationsResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
    )
    def recommendations(
        tenant: Annotated[str, Path(min_length=1, max_length=64)],
        student_id: Annotated[str, Path(min_length=1, max_length=64)],
        who: Annotated[Principal, Depends(principal)],
        k: Annotated[int, Query(ge=1, le=MAX_K, description="Quantidade de aulas")] = 10,
    ) -> RecommendationsResponse:
        if who.tenant != tenant:
            raise ForbiddenError("o token pertence a outro estúdio")
        recommender = tenants.get(tenant)
        if recommender is None:
            raise StudentNotFoundError(student_id)
        if identity.member_id(who) != student_id:
            raise ForbiddenError("o aluno só acessa as próprias recomendações")
        return build_response(recommender, student_id, k)

    return router
