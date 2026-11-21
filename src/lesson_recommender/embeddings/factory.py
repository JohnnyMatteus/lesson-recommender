"""Escolhe a implementação da porta de embeddings a partir da configuração."""

from __future__ import annotations

from enum import StrEnum

from lesson_recommender.domain.errors import ConfigurationError
from lesson_recommender.domain.ports import EmbeddingProvider
from lesson_recommender.embeddings.hashing import HashingEmbedder


class EmbeddingBackend(StrEnum):
    HASHING = "hashing"
    SENTENCE_TRANSFORMERS = "sentence-transformers"


def build_embedder(backend: str, *, model_name: str, dimensions: int) -> EmbeddingProvider:
    try:
        choice = EmbeddingBackend(backend)
    except ValueError as error:
        valid = ", ".join(item.value for item in EmbeddingBackend)
        raise ConfigurationError(
            f"backend de embeddings inválido: {backend!r} ({valid})"
        ) from error
    if choice is EmbeddingBackend.HASHING:
        return HashingEmbedder(dimensions=dimensions)
    from lesson_recommender.embeddings.sentence import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(model_name)
