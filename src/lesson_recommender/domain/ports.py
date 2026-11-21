"""Portas (interfaces) do núcleo. Adaptadores: memória, Neo4j, hashing, sentence-transformers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from lesson_recommender.domain.models import (
    CollaborativeSignal,
    Instructor,
    Lesson,
    Modality,
    Student,
    StudentHistory,
)

Vector = NDArray[np.float64]
Matrix = NDArray[np.float64]


class EmbeddingProvider(Protocol):
    """Transforma textos em vetores com norma L2 igual a 1 (linhas de zeros para texto vazio)."""

    @property
    def name(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> Matrix: ...


class CatalogRepository(Protocol):
    """Leitura do catálogo, dos alunos e do histórico de interações."""

    def get_student(self, student_id: str) -> Student | None: ...

    def list_lessons(self) -> Sequence[Lesson]: ...

    def modalities(self) -> Mapping[str, Modality]: ...

    def instructors(self) -> Mapping[str, Instructor]: ...

    def history(self, student_id: str) -> StudentHistory: ...

    def popularity(self) -> Mapping[str, int]:
        """Quantidade de alunos distintos que reservaram cada aula."""
        ...


class CollaborativeSource(Protocol):
    """Sinal colaborativo por vizinhança de alunos."""

    def neighbor_scores(
        self, student_id: str, *, neighbors: int
    ) -> Mapping[str, CollaborativeSignal]: ...


class BookingRepository(Protocol):
    """Gravação de reservas."""

    def record_booking(self, student_id: str, lesson_id: str, booked_at: datetime) -> bool:
        """Grava a reserva e ocupa uma vaga. Devolve False se a aula lotou antes da gravação."""
        ...
