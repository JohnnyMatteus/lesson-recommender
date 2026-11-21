"""Composição da aplicação: lê a configuração e conecta adaptadores às portas."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI
from neo4j import Driver, GraphDatabase

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.api.app import create_app
from lesson_recommender.api.tenant_routes import build_tenant_router
from lesson_recommender.config import RepositoryBackend, Settings
from lesson_recommender.dataset.io import load_dataset
from lesson_recommender.domain.errors import ConfigurationError
from lesson_recommender.embeddings.factory import build_embedder
from lesson_recommender.graph.repository import Neo4jRepository
from lesson_recommender.observability import configure_logging, configure_tracing
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender
from lesson_recommender.saas.auth import TokenVerifier, jwks_signing_key, static_signing_key
from lesson_recommender.saas.client import (
    SaasApiClient,
    SaasIdentityClient,
    ServiceCredentials,
    ServiceTokenProvider,
)
from lesson_recommender.saas.identity import CachedIdentityResolver
from lesson_recommender.saas.sync import TenantSyncer
from lesson_recommender.saas.tenants import TenantRecommenders

logger = logging.getLogger(__name__)


def neo4j_driver(settings: Settings) -> Driver:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    driver.verify_connectivity()
    return driver


def build_recommender(settings: Settings, driver: Driver | None = None) -> HybridRecommender:
    repository: InMemoryRepository | Neo4jRepository
    if settings.repository_backend is RepositoryBackend.NEO4J:
        if driver is None:
            raise ValueError("backend neo4j requer um driver")
        repository = Neo4jRepository(driver, database=settings.neo4j_database)
    else:
        repository = InMemoryRepository(load_dataset(settings.dataset_path))

    logger.info(
        "recomendador pronto",
        extra={
            "repository": settings.repository_backend.value,
            "lessons": len(repository.list_lessons()),
        },
    )
    return assemble(repository, settings)


def assemble(
    repository: InMemoryRepository | Neo4jRepository, settings: Settings
) -> HybridRecommender:
    embedder = build_embedder(
        settings.embeddings_backend,
        model_name=settings.embeddings_model,
        dimensions=settings.embeddings_dimensions,
    )
    content = ContentModel(
        embedder, repository.list_lessons(), repository.modalities(), repository.instructors()
    )
    return HybridRecommender(
        repository,
        repository,
        content,
        weights=settings.weights(),
        neighbors=settings.neighbors,
    )


def _signing_key(settings: Settings) -> Callable[[str], Any]:
    if settings.saas_jwt_public_key_file is not None:
        return static_signing_key(settings.saas_jwt_public_key_file.read_text())
    if settings.saas_jwks_url is None:
        raise ConfigurationError("defina LR_SAAS_JWKS_URL ou LR_SAAS_JWT_PUBLIC_KEY_FILE")
    return jwks_signing_key(settings.saas_jwks_url)


def build_saas_integration(
    settings: Settings, http: httpx.Client
) -> tuple[APIRouter, TenantSyncer]:
    if settings.saas_api_url is None or settings.saas_token_url is None:
        raise ConfigurationError("defina LR_SAAS_API_URL e LR_SAAS_TOKEN_URL")
    tenants = TenantRecommenders(lambda dataset: assemble(InMemoryRepository(dataset), settings))
    clients = {
        slug: SaasApiClient(
            http,
            settings.saas_api_url,
            ServiceTokenProvider(
                http,
                ServiceCredentials(
                    settings.saas_token_url,
                    credential.client_id,
                    credential.client_secret.get_secret_value(),
                ),
            ),
        )
        for slug, credential in settings.saas_tenants.items()
    }
    verifier = TokenVerifier(
        _signing_key(settings), issuer=settings.saas_issuer, audience=settings.saas_audience
    )
    identity = CachedIdentityResolver(SaasIdentityClient(http, settings.saas_api_url))
    syncer = TenantSyncer(
        clients,
        tenants,
        lookback_days=settings.saas_lookback_days,
        lookahead_days=settings.saas_lookahead_days,
    )
    return build_tenant_router(verifier, identity, tenants), syncer


def create_production_app() -> FastAPI:
    """Fábrica para o uvicorn.

    Uso: `uvicorn --factory lesson_recommender.bootstrap:create_production_app`.
    """
    settings = Settings()
    configure_logging(settings.log_level)
    configure_tracing(settings.otel_service_name, settings.otel_exporter_otlp_endpoint)
    saas_mode = settings.saas_api_url is not None
    http = httpx.Client(timeout=10.0)
    tenant_router: APIRouter | None = None
    syncer: TenantSyncer | None = None
    driver = None
    recommender = None
    if saas_mode:
        tenant_router, syncer = build_saas_integration(settings, http)
    else:
        if settings.repository_backend is RepositoryBackend.NEO4J:
            driver = neo4j_driver(settings)
        recommender = build_recommender(settings, driver)
    app = create_app(recommender, tenant_router=tenant_router, cors_origins=settings.cors_origins)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = None
        if syncer is not None:
            task = asyncio.create_task(_sync_forever(syncer, settings.saas_refresh_seconds))
        yield
        if task is not None:
            task.cancel()
        http.close()
        if driver is not None:
            driver.close()

    app.router.lifespan_context = lifespan
    return app


async def _sync_forever(syncer: TenantSyncer, interval_seconds: int) -> None:
    while True:
        await asyncio.to_thread(syncer.sync_all)
        await asyncio.sleep(interval_seconds)
