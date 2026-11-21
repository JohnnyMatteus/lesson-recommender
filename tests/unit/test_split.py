from dataclasses import replace

import pytest

from lesson_recommender.domain.models import Dataset
from lesson_recommender.evaluation.split import temporal_split
from tests.factories import booking, rating, studio


def dataset_with_future() -> Dataset:
    base = studio()
    future = (
        booking("ana", "y2", 20),  # descoberta nova: relevante
        booking("ana", "y1", 21),  # repetição: não conta
        booking("eva", "y1", 22),  # eva não tem treino: cold start, fora
        booking("bia", "y3", 23),  # descoberta nova de bia
        booking("caio", "p1", 24),  # repetição
    )
    return replace(
        base,
        bookings=base.bookings + future,
        ratings=(*base.ratings, rating("ana", "y2", 4, 20)),
    )


def test_relevant_items_are_first_time_bookings_after_cutoff() -> None:
    split = temporal_split(dataset_with_future(), test_fraction=0.45)
    assert split.relevant == {"ana": frozenset({"y2"}), "bia": frozenset({"y3"})}
    assert split.test_bookings == 5


def test_no_interaction_after_cutoff_leaks_into_train() -> None:
    split = temporal_split(dataset_with_future(), test_fraction=0.45)
    assert all(b.booked_at < split.cutoff for b in split.train.bookings)
    assert all(r.rated_at < split.cutoff for r in split.train.ratings)
    assert len(split.train.ratings) == 1


def test_catalog_and_students_are_preserved() -> None:
    data = dataset_with_future()
    split = temporal_split(data, test_fraction=0.45)
    assert split.train.lessons == data.lessons
    assert split.train.students == data.students


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.2])
def test_invalid_fraction(fraction: float) -> None:
    with pytest.raises(ValueError, match="test_fraction"):
        temporal_split(studio(), test_fraction=fraction)


def test_empty_dataset_cannot_be_split() -> None:
    with pytest.raises(ValueError, match="sem reservas"):
        temporal_split(replace(studio(), bookings=()))
