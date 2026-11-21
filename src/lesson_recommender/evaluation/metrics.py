"""Métricas de ranqueamento top-k com relevância binária.

Convenções (as mesmas dos testes calculados à mão em tests/unit/test_metrics.py):
- `recommended` é a lista ordenada; só os k primeiros contam; itens repetidos são proibidos.
- precision@k divide por k, mesmo que a lista tenha menos de k itens (lista curta é penalizada).
- recall@k divide pelo total de relevantes; exige ao menos um relevante.
- AP@k divide por min(|relevantes|, k), para que o ideal valha 1 mesmo com muitos relevantes.
- NDCG@k usa ganho 1 e desconto 1/log2(posição + 1), normalizado pelo ranking ideal.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence, Set


def _check(recommended: Sequence[str], k: int) -> None:
    if k <= 0:
        raise ValueError(f"k deve ser positivo: {k}")
    if len(set(recommended)) != len(recommended):
        raise ValueError("a lista recomendada contém itens repetidos")


def _check_relevant(relevant: Set[str]) -> None:
    if not relevant:
        raise ValueError("é preciso ao menos um item relevante")


def precision_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    _check(recommended, k)
    hits = sum(1 for item in recommended[:k] if item in relevant)
    return hits / k


def recall_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    _check(recommended, k)
    _check_relevant(relevant)
    hits = sum(1 for item in recommended[:k] if item in relevant)
    return hits / len(relevant)


def average_precision_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    _check(recommended, k)
    _check_relevant(relevant)
    hits = 0
    total = 0.0
    for position, item in enumerate(recommended[:k], start=1):
        if item in relevant:
            hits += 1
            total += hits / position
    return total / min(len(relevant), k)


def dcg_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    _check(recommended, k)
    return sum(
        1.0 / math.log2(position + 1)
        for position, item in enumerate(recommended[:k], start=1)
        if item in relevant
    )


def ndcg_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    _check_relevant(relevant)
    ideal = sum(1.0 / math.log2(position + 1) for position in range(1, min(len(relevant), k) + 1))
    return dcg_at_k(recommended, relevant, k) / ideal


def catalog_coverage(recommendations: Iterable[Sequence[str]], catalog_size: int, k: int) -> float:
    """Fração do catálogo que aparece em ao menos um top-k."""
    if catalog_size <= 0:
        raise ValueError(f"catalog_size deve ser positivo: {catalog_size}")
    if k <= 0:
        raise ValueError(f"k deve ser positivo: {k}")
    seen = {item for items in recommendations for item in items[:k]}
    return len(seen) / catalog_size


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("média de lista vazia")
    return sum(values) / len(values)
