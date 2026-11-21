import pytest

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.domain.errors import StudentNotFoundError
from lesson_recommender.domain.rules import EligibilityPolicy
from lesson_recommender.evaluation.baselines import PopularityRecommender, RandomRecommender
from tests.factories import studio

POLICY = EligibilityPolicy(enforce_capacity=False)


def test_popularity_orders_by_distinct_students_and_applies_rules() -> None:
    repo = InMemoryRepository(studio())
    # eva (iniciante, sem histórico): y1 (2 alunos) > y2 (1) > y3 (0). p1 e x1 fora do nível.
    assert PopularityRecommender(repo, POLICY).rank("eva", 5) == ["y1", "y2", "y3"]


def test_random_is_reproducible_per_seed_and_student() -> None:
    repo = InMemoryRepository(studio())
    first = RandomRecommender(repo, POLICY, seed=7).rank("eva", 5)
    again = RandomRecommender(repo, POLICY, seed=7).rank("eva", 5)
    assert first == again
    assert sorted(first) == ["y1", "y2", "y3"]


def test_baselines_exclude_already_booked() -> None:
    repo = InMemoryRepository(studio())
    assert "y1" not in PopularityRecommender(repo, POLICY).rank("ana", 5)
    assert "y1" not in RandomRecommender(repo, POLICY, seed=1).rank("ana", 5)


def test_unknown_student() -> None:
    with pytest.raises(StudentNotFoundError):
        PopularityRecommender(InMemoryRepository(studio()), POLICY).rank("ninguem", 3)
