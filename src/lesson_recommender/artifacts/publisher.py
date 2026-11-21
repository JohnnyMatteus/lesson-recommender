"""Publica os artefatos de uma execução, versionados por data: `<prefixo>/<AAAA-MM-DD>/...`."""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from lesson_recommender.artifacts.store import ArtifactStore
from lesson_recommender.domain.models import Instructor, Lesson, Modality
from lesson_recommender.domain.ports import EmbeddingProvider
from lesson_recommender.recommender.content import lesson_document


@dataclass(frozen=True, slots=True)
class PublishedArtifacts:
    embeddings_index: str
    embeddings_manifest: str
    report: str


def embeddings_index(
    embedder: EmbeddingProvider,
    lessons: Sequence[Lesson],
    modalities: dict[str, Modality],
    instructors: dict[str, Instructor],
) -> tuple[bytes, bytes]:
    """Matriz de vetores das aulas (.npy) e manifesto JSON com a ordem dos ids e o embedder."""
    documents = [
        lesson_document(lesson, modalities[lesson.modality_id], instructors[lesson.instructor_id])
        for lesson in lessons
    ]
    matrix = embedder.embed(documents)
    buffer = io.BytesIO()
    np.save(buffer, matrix, allow_pickle=False)
    manifest = {
        "embedder": embedder.name,
        "dimensions": int(matrix.shape[1]),
        "lesson_ids": [lesson.id for lesson in lessons],
    }
    return buffer.getvalue(), json.dumps(manifest, ensure_ascii=False, indent=1).encode()


def publish(
    store: ArtifactStore,
    *,
    run_date: date,
    index: bytes,
    manifest: bytes,
    report_markdown: str,
    prefix: str = "runs",
) -> PublishedArtifacts:
    base = f"{prefix}/{run_date.isoformat()}"
    return PublishedArtifacts(
        embeddings_index=store.put(
            f"{base}/embeddings/lessons.npy", index, content_type="application/octet-stream"
        ),
        embeddings_manifest=store.put(
            f"{base}/embeddings/manifest.json", manifest, content_type="application/json"
        ),
        report=store.put(
            f"{base}/avaliacao.md",
            report_markdown.encode(),
            content_type="text/markdown; charset=utf-8",
        ),
    )
