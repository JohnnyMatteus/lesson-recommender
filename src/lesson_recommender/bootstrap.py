"""Composição da aplicação: lê a configuração e conecta adaptadores às portas."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from neo4j import Driver, GraphDatabase
from redis import Redis

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.adapters.redis_cache import RedisRecommendationCache
from lesson_recommender.api.app import create_app
from lesson_recommender.application.booking import BookLesson
from lesson_recommender.config import RepositoryBackend, Settings
from lesson_recommender.dataset.io import load_dataset
from lesson_recommender.embeddings.factory import build_embedder
from lesson_recommender.graph.repository import Neo4jRepository
from lesson_recommender.observability import configure_logging, configure_tracing
from lesson_recommender.recommender.cached import CachedRecommender
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender
from lesson_recommender.recommender.ports import RecommendationCache, Recommender

logger = logging.getLogger(__name__)


def neo4j_driver(settings: Settings) -> Driver:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    driver.verify_connectivity()
    return driver


def build_repository(
    settings: Settings, driver: Driver | None = None
) -> InMemoryRepository | Neo4jRepository:
    if settings.repository_backend is RepositoryBackend.NEO4J:
        if driver is None:
            raise ValueError("backend neo4j requer um driver")
        return Neo4jRepository(driver, database=settings.neo4j_database)
    return InMemoryRepository(load_dataset(settings.dataset_path))


def build_recommender(
    settings: Settings, repository: InMemoryRepository | Neo4jRepository
) -> HybridRecommender:
    embedder = build_embedder(
        settings.embeddings_backend,
        model_name=settings.embeddings_model,
        dimensions=settings.embeddings_dimensions,
    )
    content = ContentModel(
        embedder, repository.list_lessons(), repository.modalities(), repository.instructors()
    )
    logger.info(
        "recomendador pronto",
        extra={
            "repository": settings.repository_backend.value,
            "embedder": embedder.name,
            "lessons": len(repository.list_lessons()),
        },
    )
    return HybridRecommender(
        repository,
        repository,
        content,
        weights=settings.weights(),
        neighbors=settings.neighbors,
    )


def build_cache(settings: Settings) -> RecommendationCache | None:
    if not settings.redis_url:
        return None
    client = Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
    logger.info(
        "cache de recomendações ativo", extra={"ttl": settings.recommendations_cache_ttl_seconds}
    )
    return RedisRecommendationCache(client, ttl_seconds=settings.recommendations_cache_ttl_seconds)


def create_production_app() -> FastAPI:
    """Fábrica para o uvicorn.

    Uso: `uvicorn --factory lesson_recommender.bootstrap:create_production_app`.
    """
    settings = Settings()
    configure_logging(settings.log_level)
    configure_tracing(settings.otel_service_name, settings.otel_exporter_otlp_endpoint)
    driver = (
        neo4j_driver(settings) if settings.repository_backend is RepositoryBackend.NEO4J else None
    )
    repository = build_repository(settings, driver)
    cache = build_cache(settings)
    recommender: Recommender = build_recommender(settings, repository)
    if cache is not None:
        recommender = CachedRecommender(recommender, cache)
    app = create_app(recommender, BookLesson(repository, repository, cache))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if driver is not None:
            driver.close()

    app.router.lifespan_context = lifespan
    return app
