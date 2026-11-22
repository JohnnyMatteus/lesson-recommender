"""Integração com o S3 local (LocalStack do docker-compose): put, get e versionamento.

Só roda com o compose no ar: defina LR_S3_ENDPOINT_URL (ex.: http://127.0.0.1:4566). Sem ela, o
teste é pulado, exceto com LR_REQUIRE_S3=1 (CI), que transforma a ausência em falha.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from lesson_recommender.artifacts.store import S3ArtifactStore, build_s3_client

pytestmark = pytest.mark.integration

ENDPOINT = os.environ.get("LR_S3_ENDPOINT_URL", "")
BUCKET = os.environ.get("LR_S3_BUCKET", "lesson-recommender-artifacts")


@pytest.fixture(scope="module")
def client() -> Any:
    if not ENDPOINT:
        if os.environ.get("LR_REQUIRE_S3") == "1":
            pytest.fail("LR_REQUIRE_S3=1, mas LR_S3_ENDPOINT_URL não está definida")
        pytest.skip("LR_S3_ENDPOINT_URL não definida (suba o compose)")
    return build_s3_client(
        ENDPOINT,
        os.environ.get("LR_S3_ACCESS_KEY", "dev-only-localstack"),
        os.environ.get("LR_S3_SECRET_KEY", "dev-only-change-me"),
        "us-east-1",
    )


def test_bucket_do_init_esta_versionado(client: Any) -> None:
    assert client.get_bucket_versioning(Bucket=BUCKET).get("Status") == "Enabled"


def test_put_e_get_pela_porta_do_projeto(client: Any) -> None:
    store = S3ArtifactStore(client, BUCKET)
    key = f"it/{uuid.uuid4()}/avaliacao.md"
    uri = store.put(key, b"# relatorio", content_type="text/markdown")
    assert uri == f"s3://{BUCKET}/{key}"
    assert store.get(key) == b"# relatorio"


def test_segunda_escrita_na_mesma_chave_guarda_as_duas_versoes(client: Any) -> None:
    store = S3ArtifactStore(client, BUCKET)
    key = f"it/{uuid.uuid4()}/manifest.json"
    store.put(key, b"v1", content_type="application/json")
    store.put(key, b"v2", content_type="application/json")
    assert store.get(key) == b"v2"
    versions = client.list_object_versions(Bucket=BUCKET, Prefix=key)["Versions"]
    assert len(versions) == 2
    first = next(v for v in versions if not v["IsLatest"])
    body = client.get_object(Bucket=BUCKET, Key=key, VersionId=first["VersionId"])["Body"].read()
    assert body == b"v1"
