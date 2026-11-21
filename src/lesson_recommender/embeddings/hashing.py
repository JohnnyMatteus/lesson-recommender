"""Embeddings determinísticos por hashing de n-gramas (feature hashing com sinal).

Não precisa de treino nem de download: o mesmo texto gera o mesmo vetor em qualquer máquina.
É o backend padrão em testes e no CI (ver docs/adr/0002-porta-de-embeddings.md).
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

import numpy as np

from lesson_recommender.domain.ports import Matrix

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {"a", "o", "as", "os", "e", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas"}
    | {"um", "uma", "com", "para", "por", "que", "se", "ao", "aos", "pela", "pelo"}
    | {"sua", "seu", "suas", "seus"}
)


def normalize_text(text: str) -> str:
    """Minúsculas e sem acentos, para que 'Respiração' e 'respiracao' coincidam."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(normalize_text(text)) if token not in _STOPWORDS]


class HashingEmbedder:
    """Unigramas e bigramas, frequência sublinear (1 + log tf), hash estável blake2b, norma L2."""

    def __init__(self, dimensions: int = 1024) -> None:
        if dimensions <= 0:
            raise ValueError(f"dimensions deve ser positivo: {dimensions}")
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return f"hashing-{self._dimensions}"

    def embed(self, texts: Sequence[str]) -> Matrix:
        matrix = np.zeros((len(texts), self._dimensions), dtype=np.float64)
        for row, text in enumerate(texts):
            tokens = tokenize(text)
            features = Counter(tokens + [f"{a}_{b}" for a, b in itertools.pairwise(tokens)])
            for feature, count in features.items():
                index, sign = self._bucket(feature)
                matrix[row, index] += sign * (1.0 + math.log(count))
            norm = float(np.linalg.norm(matrix[row]))
            if norm > 0:
                matrix[row] /= norm
        return matrix

    def _bucket(self, feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        sign = 1.0 if value & 1 else -1.0
        return (value >> 1) % self._dimensions, sign
