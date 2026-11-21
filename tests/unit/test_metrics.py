"""Métricas conferidas com contas feitas à mão (valores comentados em cada caso)."""

import math
from collections.abc import Callable, Sequence, Set

import pytest

from lesson_recommender.evaluation.metrics import (
    average_precision_at_k,
    catalog_coverage,
    dcg_at_k,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

RECOMMENDED = ["a", "b", "c", "d", "e"]
RELEVANT = {"a", "c", "f"}


def test_precision_counts_hits_in_top_k_over_k() -> None:
    # top-5 tem a e c: 2/5. top-3 tem a e c: 2/3. top-2 tem só a: 1/2.
    assert precision_at_k(RECOMMENDED, RELEVANT, 5) == pytest.approx(0.4)
    assert precision_at_k(RECOMMENDED, RELEVANT, 3) == pytest.approx(2 / 3)
    assert precision_at_k(RECOMMENDED, RELEVANT, 2) == pytest.approx(0.5)


def test_recall_divides_by_all_relevant_including_unreachable() -> None:
    # f nunca foi recomendado: recall@5 = 2/3, mesmo com 5 posições.
    assert recall_at_k(RECOMMENDED, RELEVANT, 5) == pytest.approx(2 / 3)
    assert recall_at_k(RECOMMENDED, RELEVANT, 1) == pytest.approx(1 / 3)


def test_average_precision_by_hand() -> None:
    # Acertos nas posições 1 e 3: (1/1 + 2/3) / min(3, 5) = 0.5556
    assert average_precision_at_k(RECOMMENDED, RELEVANT, 5) == pytest.approx((1 + 2 / 3) / 3)


def test_ndcg_by_hand() -> None:
    # DCG = 1/log2(2) + 1/log2(4) = 1.5
    # IDCG (3 relevantes) = 1 + 1/log2(3) + 1/log2(4) = 2.1309
    assert dcg_at_k(RECOMMENDED, RELEVANT, 5) == pytest.approx(1.5)
    ideal = 1 + 1 / math.log2(3) + 0.5
    assert ndcg_at_k(RECOMMENDED, RELEVANT, 5) == pytest.approx(1.5 / ideal)
    assert ndcg_at_k(RECOMMENDED, RELEVANT, 5) == pytest.approx(0.70392, abs=1e-5)


def test_position_matters_for_ndcg_and_ap_but_not_precision() -> None:
    early = ["a", "x", "y"]
    late = ["x", "y", "a"]
    relevant = {"a"}
    assert precision_at_k(early, relevant, 3) == precision_at_k(late, relevant, 3)
    assert ndcg_at_k(early, relevant, 3) == pytest.approx(1.0)
    assert ndcg_at_k(late, relevant, 3) == pytest.approx(0.5)  # 1/log2(4)
    assert average_precision_at_k(late, relevant, 3) == pytest.approx(1 / 3)


def test_perfect_ranking_scores_one() -> None:
    recommended = ["a", "c", "f", "x"]
    assert ndcg_at_k(recommended, RELEVANT, 3) == pytest.approx(1.0)
    assert average_precision_at_k(recommended, RELEVANT, 3) == pytest.approx(1.0)
    assert recall_at_k(recommended, RELEVANT, 3) == pytest.approx(1.0)


def test_more_relevant_than_k_still_allows_perfect_ap_and_ndcg() -> None:
    # 4 relevantes e k=2: AP divide por min(4, 2) = 2; recall fica em 2/4.
    recommended = ["a", "b"]
    relevant = {"a", "b", "c", "d"}
    assert average_precision_at_k(recommended, relevant, 2) == pytest.approx(1.0)
    assert ndcg_at_k(recommended, relevant, 2) == pytest.approx(1.0)
    assert recall_at_k(recommended, relevant, 2) == pytest.approx(0.5)


def test_short_list_is_penalized_in_precision_only() -> None:
    assert precision_at_k(["a"], {"a"}, 5) == pytest.approx(0.2)
    assert recall_at_k(["a"], {"a"}, 5) == pytest.approx(1.0)
    assert ndcg_at_k(["a"], {"a"}, 5) == pytest.approx(1.0)


def test_no_hits_scores_zero() -> None:
    assert precision_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert recall_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert ndcg_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert average_precision_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert ndcg_at_k([], {"a"}, 3) == 0.0


@pytest.mark.parametrize("k", [0, -1])
def test_non_positive_k_is_rejected(k: int) -> None:
    with pytest.raises(ValueError, match="k deve ser positivo"):
        precision_at_k(RECOMMENDED, RELEVANT, k)


def test_duplicates_are_rejected() -> None:
    with pytest.raises(ValueError, match="repetidos"):
        precision_at_k(["a", "a"], {"a"}, 2)


@pytest.mark.parametrize("metric", [recall_at_k, average_precision_at_k, ndcg_at_k])
def test_metrics_that_need_relevant_items_reject_empty_set(
    metric: Callable[[Sequence[str], Set[str], int], float],
) -> None:
    with pytest.raises(ValueError, match="relevante"):
        metric(["a"], set(), 1)


def test_catalog_coverage_counts_distinct_items_in_top_k() -> None:
    lists = [["a", "b"], ["b", "c"]]
    assert catalog_coverage(lists, 10, 2) == pytest.approx(0.3)
    assert catalog_coverage(lists, 10, 1) == pytest.approx(0.2)


def test_catalog_coverage_validates_inputs() -> None:
    with pytest.raises(ValueError, match="catalog_size"):
        catalog_coverage([["a"]], 0, 1)
    with pytest.raises(ValueError, match="k deve ser positivo"):
        catalog_coverage([["a"]], 1, 0)


def test_mean_of_empty_list_fails_explicitly() -> None:
    assert mean([1.0, 2.0]) == pytest.approx(1.5)
    with pytest.raises(ValueError, match="vazia"):
        mean([])
