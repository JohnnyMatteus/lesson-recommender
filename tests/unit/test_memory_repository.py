from dataclasses import replace

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from tests.factories import rating, studio


def test_history_aggregates_repeated_bookings() -> None:
    repo = InMemoryRepository(studio())
    history = repo.history("ana")
    assert history.bookings == {"y1": 2}
    assert history.ratings == {}


def test_latest_rating_wins_regardless_of_input_order() -> None:
    dataset = studio()
    later = rating("bia", "y2", 2, day=30)
    repo = InMemoryRepository(replace(dataset, ratings=(later, *dataset.ratings)))
    assert repo.history("bia").ratings == {"y2": 2}


def test_popularity_counts_distinct_students() -> None:
    repo = InMemoryRepository(studio())
    # y1: ana (2 reservas) e bia -> 2 alunos distintos
    assert repo.popularity()["y1"] == 2
    assert repo.popularity()["p1"] == 2
    assert "x1" not in repo.popularity()


def test_unknown_student() -> None:
    repo = InMemoryRepository(studio())
    assert repo.get_student("ninguem") is None
    assert repo.history("ninguem").bookings == {}
    assert repo.neighbor_scores("ninguem", neighbors=5) == {}
