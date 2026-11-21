import pytest

from lesson_recommender.recommender.collaborative import (
    UNRATED_WEIGHT,
    jaccard,
    neighborhood_scores,
)

# u = {A, B}
# v1 = {A, B, C}  jaccard 2/3; avaliou C com 5 (peso 1.0)
# v2 = {B, D}     jaccard 1/3; não avaliou D (peso 0.6)
# v4 = {A, C}     jaccard 1/3; avaliou C com 2 (peso 0.4)
# v3 = {E}        sem interseção: não é vizinho
BOOKED = {
    "u": frozenset({"A", "B"}),
    "v1": frozenset({"A", "B", "C"}),
    "v2": frozenset({"B", "D"}),
    "v3": frozenset({"E"}),
    "v4": frozenset({"A", "C"}),
}
RATINGS = {("v1", "C"): 5, ("v4", "C"): 2}


def test_jaccard() -> None:
    assert jaccard({"A", "B"}, {"A", "B", "C"}) == pytest.approx(2 / 3)
    assert jaccard(set(), set()) == 0.0


def test_scores_by_hand_with_all_neighbors() -> None:
    scores = neighborhood_scores("u", BOOKED, RATINGS, neighbors=10)
    # C = 2/3 * 1.0 + 1/3 * 0.4 = 0.8 (2 vizinhos); D = 1/3 * 0.6 = 0.2 (1 vizinho)
    assert set(scores) == {"C", "D"}
    assert scores["C"].score == pytest.approx(0.8)
    assert scores["C"].support == 2
    assert scores["D"].score == pytest.approx(1 / 3 * UNRATED_WEIGHT)
    assert scores["D"].support == 1


def test_neighbor_limit_breaks_ties_by_student_id() -> None:
    # v2 e v4 empatam em 1/3; com 2 vizinhos entra v2 (menor id), então C = 2/3 apenas.
    scores = neighborhood_scores("u", BOOKED, RATINGS, neighbors=2)
    assert scores["C"].score == pytest.approx(2 / 3)
    assert scores["C"].support == 1
    assert scores["D"].score == pytest.approx(0.2)


def test_never_recommends_what_the_student_already_booked() -> None:
    scores = neighborhood_scores("u", BOOKED, RATINGS, neighbors=10)
    assert not set(scores) & BOOKED["u"]


def test_student_without_history_gets_no_signal() -> None:
    assert neighborhood_scores("novo", BOOKED, RATINGS, neighbors=5) == {}


def test_neighbors_must_be_positive() -> None:
    with pytest.raises(ValueError, match="neighbors"):
        neighborhood_scores("u", BOOKED, RATINGS, neighbors=0)
