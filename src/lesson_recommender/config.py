"""Configuração por variáveis de ambiente (prefixo LR_). Ver .env.example."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from lesson_recommender.recommender.hybrid import Weights


class RepositoryBackend(StrEnum):
    MEMORY = "memory"
    NEO4J = "neo4j"


class ArtifactsBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class TenantCredential(BaseModel):
    client_id: str
    client_secret: SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LR_", env_file=".env", extra="ignore")

    repository_backend: RepositoryBackend = RepositoryBackend.MEMORY
    dataset_path: Path = Path("data/dataset.json")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("dev-only-change-me")
    neo4j_database: str | None = None

    embeddings_backend: str = "hashing"
    embeddings_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings_dimensions: int = Field(default=1024, gt=0)

    weight_content: float = Field(default=0.3, ge=0)
    weight_collaborative: float = Field(default=0.6, ge=0)
    weight_popularity: float = Field(default=0.1, ge=0)
    neighbors: int = Field(default=30, gt=0)

    artifacts_backend: ArtifactsBackend = ArtifactsBackend.LOCAL
    artifacts_dir: Path = Path("artifacts")
    s3_endpoint_url: str | None = None
    s3_bucket: str = "lesson-recommender-artifacts"
    s3_access_key: str = "dev-only-minio"
    s3_secret_key: SecretStr = SecretStr("dev-only-change-me")
    s3_region: str = "us-east-1"

    # Integração com o SaaS (ADR 0009). Sem `saas_api_url`, a API serve só o dataset sintético.
    saas_api_url: str | None = None
    saas_token_url: str | None = None
    saas_issuer: str = "http://localhost:8080/realms/estudios"
    saas_audience: str = "studio-api"
    saas_jwks_url: str | None = None
    saas_jwt_public_key_file: Path | None = None
    saas_tenants: dict[str, TenantCredential] = Field(default_factory=dict)
    saas_refresh_seconds: int = Field(default=300, gt=0)
    saas_lookback_days: int = Field(default=90, gt=0)
    saas_lookahead_days: int = Field(default=14, ge=0)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    redis_url: str | None = None
    recommendations_cache_ttl_seconds: int = Field(default=120, gt=0)

    log_level: str = "INFO"
    otel_service_name: str = "lesson-recommender"
    otel_exporter_otlp_endpoint: str | None = None

    def weights(self) -> Weights:
        return Weights(
            content=self.weight_content,
            collaborative=self.weight_collaborative,
            popularity=self.weight_popularity,
        )
