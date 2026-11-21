import pytest

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.domain.errors import InvalidRequestError, StudentNotFoundError
from lesson_recommender.domain.rules import EligibilityPolicy
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import (
    HybridRecommender,
    Weights,
    min_max,
    share_of_max,
)
from tests.factories import studio


def build(
    weights: Weights | None = None, policy: EligibilityPolicy | None = None
) -> HybridRecommender:
    repo = InMemoryRepository(studio())
    content = ContentModel(
        HashingEmbedder(512), repo.list_lessons(), repo.modalities(), repo.instructors()
    )
    return HybridRecommender(repo, repo, content, weights=weights, policy=policy, neighbors=10)


def ids(recommender: HybridRecommender, student_id: str, k: int = 10) -> list[str]:
    return recommender.rank(student_id, k)


def test_never_recommends_booked_full_or_out_of_level_lessons() -> None:
    # ana: iniciante, já fez y1. y3 está lotada, p1 é intermediária, x1 é avançada.
    assert ids(build(), "ana") == ["y2"]


def test_capacity_rule_respects_policy() -> None:
    relaxed = build(policy=EligibilityPolicy(enforce_capacity=False))
    assert set(ids(relaxed, "ana")) == {"y2", "y3"}


def test_contraindicated_lesson_is_excluded_even_at_right_level() -> None:
    # duda é avançada e gestante: x1 bate o nível, mas é contraindicada.
    relaxed = build(policy=EligibilityPolicy(enforce_restrictions=False))
    assert ids(relaxed, "duda") == ["x1"]
    assert ids(build(), "duda") == []


def test_collaborative_signal_from_similar_student() -> None:
    # ana e bia compartilham y1; bia fez y2 (nota 5). Só com colaborativo, y2 lidera.
    recommender = build(Weights(content=0.0, collaborative=1.0, popularity=0.0))
    [top] = recommender.recommend("ana", 1)
    assert top.lesson.id == "y2"
    assert top.breakdown.collaborative == pytest.approx(1.0)
    assert any("1 aluno com histórico parecido" in reason for reason in top.reasons)


def test_reasons_only_mention_active_signals() -> None:
    recommender = build(Weights(content=1.0, collaborative=0.0, popularity=0.0))
    [top] = recommender.recommend("ana", 1)
    assert not any("histórico parecido" in reason for reason in top.reasons)
    assert any("flexibilidade" in reason for reason in top.reasons)
    assert any("que você já frequenta" in reason for reason in top.reasons)


def test_cold_start_student_still_gets_recommendations() -> None:
    # eva não tem histórico: objetivos (conteúdo) e popularidade resolvem.
    result = build().recommend("eva", 3)
    assert {item.lesson.id for item in result} == {"y1", "y2"}
    assert all(item.breakdown.collaborative == 0.0 for item in result)


def test_ranking_is_sorted_and_deterministic() -> None:
    recommender = build()
    first = recommender.recommend("eva", 5)
    second = recommender.recommend("eva", 5)
    assert first == second
    scores = [item.score for item in first]
    assert scores == sorted(scores, reverse=True)


def test_empty_when_nothing_is_eligible() -> None:
    # duda (avançada, gestante): p1 já reservada, x1 contraindicada, yoga iniciante fora do nível.
    assert build().recommend("duda", 5) == []


def test_unknown_student_raises() -> None:
    with pytest.raises(StudentNotFoundError):
        build().recommend("ninguem", 5)


@pytest.mark.parametrize("k", [0, 51])
def test_k_out_of_range_raises(k: int) -> None:
    with pytest.raises(InvalidRequestError):
        build().recommend("ana", k)


@pytest.mark.parametrize(
    "values", [(-0.1, 0.5, 0.5), (0.0, 0.0, 0.0)], ids=["negativo", "todos-zero"]
)
def test_invalid_weights(values: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="peso"):
        Weights(*values)


def test_normalizers() -> None:
    assert min_max({"a": 1.0, "b": 3.0}) == {"a": 0.0, "b": 1.0}
    assert min_max({"a": 2.0, "b": 2.0}) == {"a": 0.0, "b": 0.0}
    assert min_max({}) == {}
    assert share_of_max({"a": 0.0, "b": 2.0}) == {"a": 0.0, "b": 1.0}
    assert share_of_max({"a": 0.0}) == {"a": 0.0}
