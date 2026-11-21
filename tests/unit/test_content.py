import numpy as np
import pytest

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.domain.models import Goal, StudentHistory
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.recommender.content import ContentModel
from tests.factories import student, studio


@pytest.fixture
def model() -> ContentModel:
    repo = InMemoryRepository(studio())
    return ContentModel(
        HashingEmbedder(512), repo.list_lessons(), repo.modalities(), repo.instructors()
    )


def test_goals_steer_profile_without_history(model: ContentModel) -> None:
    strength = student("s", goals=(Goal.STRENGTH,))
    scores = model.scores(model.profile(strength, StudentHistory({}, {})), ["y1", "p1"])
    assert scores["p1"] > scores["y1"]


def test_history_pulls_profile_towards_booked_lessons(model: ContentModel) -> None:
    yoga_fan = student("s", goals=(Goal.STRENGTH,))
    history = StudentHistory(bookings={"y1": 10}, ratings={"y1": 5})
    scores = model.scores(model.profile(yoga_fan, history), ["y2", "p1"])
    assert scores["y2"] > scores["p1"]


def test_profile_is_unit_norm(model: ContentModel) -> None:
    profile = model.profile(student("s"), StudentHistory({"y1": 2}, {}))
    assert np.linalg.norm(profile) == pytest.approx(1.0)


def test_most_similar_ignores_the_lesson_itself(model: ContentModel) -> None:
    similar = model.most_similar("y1", ["y1", "y2", "p1"])
    assert similar is not None
    assert similar[0] == "y2"
    assert model.most_similar("y1", ["y1"]) is None


def test_goal_weight_is_validated() -> None:
    repo = InMemoryRepository(studio())
    with pytest.raises(ValueError, match="goal_weight"):
        ContentModel(
            HashingEmbedder(8),
            repo.list_lessons(),
            repo.modalities(),
            repo.instructors(),
            goal_weight=1.5,
        )
