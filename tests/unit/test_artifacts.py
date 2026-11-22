import io
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.artifacts.publisher import embeddings_index, publish
from lesson_recommender.artifacts.store import LocalArtifactStore, S3ArtifactStore
from lesson_recommender.embeddings.hashing import HashingEmbedder
from tests.factories import studio


class FakeS3Client:
    """Imita o subconjunto de boto3 usado pelo adaptador (put_object/get_object)."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = (Body, ContentType)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)][0])}


def _index() -> tuple[bytes, bytes]:
    repo = InMemoryRepository(studio())
    return embeddings_index(
        HashingEmbedder(32),
        repo.list_lessons(),
        dict(repo.modalities()),
        dict(repo.instructors()),
    )


def test_local_store_roundtrip(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    uri = store.put("runs/x/a.txt", b"oi", content_type="text/plain")
    assert uri.startswith("file://")
    assert store.get("runs/x/a.txt") == b"oi"
    with pytest.raises(FileNotFoundError):
        store.get("runs/x/nada.txt")


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../fora.txt", "runs/../../x"])
def test_keys_cannot_escape_the_store(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="chave"):
        LocalArtifactStore(tmp_path).put(key, b"x", content_type="text/plain")


def test_s3_store_uses_bucket_and_content_type() -> None:
    client = FakeS3Client()
    store = S3ArtifactStore(client, "artefatos")
    assert store.put("a/b.md", b"# r", content_type="text/markdown") == "s3://artefatos/a/b.md"
    assert client.objects[("artefatos", "a/b.md")] == (b"# r", "text/markdown")
    assert store.get("a/b.md") == b"# r"


def test_embeddings_index_matches_manifest() -> None:
    index, manifest = _index()
    matrix = np.load(io.BytesIO(index), allow_pickle=False)
    data = json.loads(manifest)
    assert data["lesson_ids"] == ["p1", "x1", "y1", "y2", "y3"]
    assert matrix.shape == (5, data["dimensions"])
    assert data["embedder"] == "hashing-32"


def test_publish_versions_artifacts_by_date() -> None:
    client = FakeS3Client()
    index, manifest = _index()
    published = publish(
        S3ArtifactStore(client, "b"),
        run_date=date(2026, 11, 21),
        index=index,
        manifest=manifest,
        report_markdown="# Relatório",
    )
    assert published.report == "s3://b/runs/2026-11-21/avaliacao.md"
    assert {key for _, key in client.objects} == {
        "runs/2026-11-21/avaliacao.md",
        "runs/2026-11-21/embeddings/lessons.npy",
        "runs/2026-11-21/embeddings/manifest.json",
    }


def test_build_s3_client_usa_path_style_com_endpoint_proprio() -> None:
    pytest.importorskip("boto3")
    from lesson_recommender.artifacts.store import build_s3_client

    client = build_s3_client("http://localstack:4566", "dev-only-a", "dev-only-b", "us-east-1")
    assert client.meta.config.s3["addressing_style"] == "path"
