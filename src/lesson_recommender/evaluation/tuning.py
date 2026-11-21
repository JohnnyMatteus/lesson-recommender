"""Ajuste dos pesos do híbrido num recorte de validação, separado do teste.

O recorte de validação sai do treino (os últimos dias antes do corte do teste), com o mesmo
protocolo temporal da avaliação. O teste nunca é consultado: assim o número reportado não é
otimista por ter sido usado para escolher os pesos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.domain.models import Dataset
from lesson_recommender.domain.ports import EmbeddingProvider
from lesson_recommender.domain.rules import EligibilityPolicy
from lesson_recommender.evaluation.metrics import mean, ndcg_at_k
from lesson_recommender.evaluation.split import temporal_split
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender, Weights


@dataclass(frozen=True, slots=True)
class TuningTrial:
    weights: Weights
    ndcg: float


@dataclass(frozen=True, slots=True)
class TuningResult:
    k: int
    cutoff: datetime
    train_bookings: int
    validation_bookings: int
    students: int
    trials: tuple[TuningTrial, ...]  # do melhor para o pior

    @property
    def best(self) -> Weights:
        return self.trials[0].weights


def weight_grid(step: float) -> list[Weights]:
    """Todas as combinações com soma 1 em passos de `step` (ordem determinística)."""
    steps = round(1.0 / step)
    if steps < 1 or abs(steps * step - 1.0) > 1e-9:
        raise ValueError(f"step deve dividir 1: {step}")
    return [
        Weights(content=c / steps, collaborative=b / steps, popularity=(steps - c - b) / steps)
        for c in range(steps + 1)
        for b in range(steps + 1 - c)
    ]


def tune_weights(
    train: Dataset,
    embedder: EmbeddingProvider,
    *,
    policy: EligibilityPolicy,
    k: int = 10,
    validation_fraction: float = 0.2,
    step: float = 0.1,
    neighbors: int = 30,
) -> TuningResult:
    inner = temporal_split(train, test_fraction=validation_fraction)
    if not inner.relevant:
        raise ValueError("nenhum aluno com descobertas no recorte de validação")
    repository = InMemoryRepository(inner.train)
    content = ContentModel(
        embedder, repository.list_lessons(), repository.modalities(), repository.instructors()
    )
    students = sorted(inner.relevant)
    trials = []
    for weights in weight_grid(step):
        model = HybridRecommender(
            repository, repository, content, weights=weights, policy=policy, neighbors=neighbors
        )
        score = mean([ndcg_at_k(model.rank(s, k), inner.relevant[s], k) for s in students])
        trials.append(TuningTrial(weights, score))
    # Empate: ordem lexicográfica dos pesos, para o resultado não depender de ponto flutuante.
    trials.sort(key=lambda t: (-round(t.ndcg, 9), t.weights.content, t.weights.collaborative))
    return TuningResult(
        k=k,
        cutoff=inner.cutoff,
        train_bookings=len(inner.train.bookings),
        validation_bookings=inner.test_bookings,
        students=len(students),
        trials=tuple(trials),
    )
