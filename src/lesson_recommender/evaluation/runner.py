"""Avaliação offline: split temporal, modelos candidatos, métricas e intervalo de confiança."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.domain.models import Dataset
from lesson_recommender.domain.ports import EmbeddingProvider
from lesson_recommender.domain.rules import EligibilityPolicy
from lesson_recommender.evaluation.baselines import (
    PopularityRecommender,
    RandomRecommender,
    RankingModel,
)
from lesson_recommender.evaluation.metrics import (
    average_precision_at_k,
    catalog_coverage,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from lesson_recommender.evaluation.split import temporal_split
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender, Weights

# A lotação é estado atual, não histórico; aplicá-la no passado puniria os modelos por algo que
# não existia na hora da reserva. Nível e contraindicação valem sempre.
EVALUATION_POLICY = EligibilityPolicy(enforce_capacity=False)


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    ks: tuple[int, ...] = (5, 10)
    test_fraction: float = 0.2
    seed: int = 42
    neighbors: int = 30
    weights: Weights = field(default_factory=Weights)
    bootstrap_samples: int = 1000

    def __post_init__(self) -> None:
        if not self.ks or any(k <= 0 for k in self.ks):
            raise ValueError(f"ks inválidos: {self.ks}")


@dataclass(frozen=True, slots=True)
class MetricSet:
    precision: float
    recall: float
    ndcg: float
    map: float
    coverage: float


@dataclass(frozen=True, slots=True)
class ModelResult:
    name: str
    description: str
    metrics: dict[int, MetricSet]
    per_user_ndcg: dict[int, list[float]]


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    baseline: str
    k: int
    mean_delta: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    config: EvaluationConfig
    embedder: str
    cutoff: datetime
    catalog_size: int
    students_total: int
    students_evaluated: int
    train_bookings: int
    test_bookings: int
    relevant_items: int
    results: list[ModelResult]
    intervals: list[ConfidenceInterval]


def _score_model(
    name: str,
    description: str,
    model: RankingModel,
    relevant: dict[str, frozenset[str]],
    ks: Sequence[int],
    catalog_size: int,
) -> ModelResult:
    students = sorted(relevant)
    depth = max(ks)
    rankings = {student: model.rank(student, depth) for student in students}
    metrics: dict[int, MetricSet] = {}
    per_user_ndcg: dict[int, list[float]] = {}
    for k in ks:
        ndcgs = [ndcg_at_k(rankings[s], relevant[s], k) for s in students]
        per_user_ndcg[k] = ndcgs
        metrics[k] = MetricSet(
            precision=mean([precision_at_k(rankings[s], relevant[s], k) for s in students]),
            recall=mean([recall_at_k(rankings[s], relevant[s], k) for s in students]),
            ndcg=mean(ndcgs),
            map=mean([average_precision_at_k(rankings[s], relevant[s], k) for s in students]),
            coverage=catalog_coverage(rankings.values(), catalog_size, k),
        )
    return ModelResult(name, description, metrics, per_user_ndcg)


def paired_bootstrap(
    model: Sequence[float], baseline: Sequence[float], *, samples: int, seed: int
) -> tuple[float, float, float]:
    """IC de 95% da diferença média (modelo - baseline), reamostrando alunos com reposição."""
    if len(model) != len(baseline) or not model:
        raise ValueError("as listas precisam ter o mesmo tamanho e não podem ser vazias")
    deltas = [a - b for a, b in zip(model, baseline, strict=True)]
    rng = random.Random(seed)
    size = len(deltas)
    means = sorted(sum(rng.choices(deltas, k=size)) / size for _ in range(samples))
    low = means[int(0.025 * (samples - 1))]
    high = means[int(0.975 * (samples - 1))]
    return mean(deltas), low, high


def evaluate(
    dataset: Dataset, embedder: EmbeddingProvider, config: EvaluationConfig | None = None
) -> EvaluationReport:
    config = config or EvaluationConfig()
    split = temporal_split(dataset, test_fraction=config.test_fraction)
    if not split.relevant:
        raise ValueError("nenhum aluno com descobertas no período de teste")
    repository = InMemoryRepository(split.train)
    content = ContentModel(
        embedder, repository.list_lessons(), repository.modalities(), repository.instructors()
    )

    def hybrid(weights: Weights) -> HybridRecommender:
        return HybridRecommender(
            repository,
            repository,
            content,
            weights=weights,
            policy=EVALUATION_POLICY,
            neighbors=config.neighbors,
        )

    w = config.weights
    candidates: list[tuple[str, str, Callable[[], RankingModel]]] = [
        (
            "aleatorio",
            "Ordem aleatória entre as elegíveis",
            lambda: RandomRecommender(repository, EVALUATION_POLICY, seed=config.seed),
        ),
        (
            "popularidade",
            "Mais alunos distintos no treino",
            lambda: PopularityRecommender(repository, EVALUATION_POLICY),
        ),
        ("conteudo", "Só embeddings (ablação)", lambda: hybrid(Weights(1.0, 0.0, 0.0))),
        (
            "colaborativo",
            "Só vizinhança de alunos, mesma conta do Cypher (ablação)",
            lambda: hybrid(Weights(0.0, 1.0, 0.0)),
        ),
        (
            "hibrido",
            f"Conteúdo {w.content} + colaborativo {w.collaborative} + popularidade {w.popularity}",
            lambda: hybrid(w),
        ),
    ]
    catalog_size = len(dataset.lessons)
    results = [
        _score_model(name, description, factory(), split.relevant, config.ks, catalog_size)
        for name, description, factory in candidates
    ]

    by_name = {result.name: result for result in results}
    intervals = []
    for baseline in ("popularidade", "aleatorio"):
        for k in config.ks:
            delta, low, high = paired_bootstrap(
                by_name["hibrido"].per_user_ndcg[k],
                by_name[baseline].per_user_ndcg[k],
                samples=config.bootstrap_samples,
                seed=config.seed,
            )
            intervals.append(ConfidenceInterval(baseline, k, delta, low, high))

    return EvaluationReport(
        config=config,
        embedder=embedder.name,
        cutoff=split.cutoff,
        catalog_size=catalog_size,
        students_total=len(dataset.students),
        students_evaluated=len(split.relevant),
        train_bookings=len(split.train.bookings),
        test_bookings=split.test_bookings,
        relevant_items=sum(len(items) for items in split.relevant.values()),
        results=results,
        intervals=intervals,
    )
