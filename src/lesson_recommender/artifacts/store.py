"""Armazenamento de artefatos do modelo (índice de embeddings e relatórios de avaliação).

Porta `ArtifactStore` com dois adaptadores:
- `LocalArtifactStore`: diretório local (padrão; testes e uso sem infraestrutura);
- `S3ArtifactStore`: qualquer serviço compatível com S3. Localmente aponta para o MinIO do
  docker-compose; na AWS, basta trocar endpoint e credenciais (ver ADR 0008).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from lesson_recommender.domain.errors import ConfigurationError


class ArtifactStore(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str) -> str:
        """Grava o artefato e devolve uma URI legível (file://... ou s3://...)."""
        ...

    def get(self, key: str) -> bytes: ...


def _validate_key(key: str) -> str:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"chave de artefato inválida: {key!r}")
    return key


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def put(self, key: str, data: bytes, *, content_type: str) -> str:
        target = self._root / _validate_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target.resolve().as_uri()

    def get(self, key: str) -> bytes:
        target = self._root / _validate_key(key)
        if not target.exists():
            raise FileNotFoundError(f"artefato não encontrado: {key}")
        return target.read_bytes()


class S3ArtifactStore:
    """Recebe um cliente boto3 já construído (injeção), o que permite testar com um falso."""

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, key: str, data: bytes, *, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket, Key=_validate_key(key), Body=data, ContentType=content_type
        )
        return f"s3://{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=_validate_key(key))
        body: bytes = response["Body"].read()
        return body


def build_s3_client(endpoint_url: str | None, access_key: str, secret_key: str, region: str) -> Any:
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - depende do ambiente
        raise ConfigurationError(
            "backend 's3' requer o extra: pip install 'lesson-recommender[s3]'"
        ) from error
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or None,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
