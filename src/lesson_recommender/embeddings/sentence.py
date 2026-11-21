"""Adaptador opcional para sentence-transformers.

Só é importado quando `LR_EMBEDDINGS_BACKEND=sentence-transformers`. O pacote fica no extra
`[sentence-transformers]` para que o CI não baixe PyTorch nem modelos.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from lesson_recommender.domain.errors import ConfigurationError
from lesson_recommender.domain.ports import Matrix


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover - depende do ambiente
            raise ConfigurationError(
                "backend 'sentence-transformers' requer o extra: "
                "pip install 'lesson-recommender[sentence-transformers]'"
            ) from error
        self._model_name = model_name
        self._model: Any = SentenceTransformer(model_name)

    @property
    def name(self) -> str:
        return f"sentence-transformers:{self._model_name}"

    def embed(self, texts: Sequence[str]) -> Matrix:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float64)
