import pytest
from fastapi.testclient import TestClient

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.api.app import create_app
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender
from tests.factories import studio


@pytest.fixture
def client() -> TestClient:
    repo = InMemoryRepository(studio())
    content = ContentModel(
        HashingEmbedder(256), repo.list_lessons(), repo.modalities(), repo.instructors()
    )
    return TestClient(create_app(HybridRecommender(repo, repo, content, neighbors=10)))


def test_recommendations_with_explanations(client: TestClient) -> None:
    response = client.get("/students/ana/recommendations", params={"k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == "ana"
    assert body["weights"] == {"content": 0.5, "collaborative": 0.4, "popularity": 0.1}
    [item] = body["items"]
    assert item["lesson"]["id"] == "y2"
    assert item["lesson"]["seats_left"] == 10
    assert item["reasons"]
    assert set(item["breakdown"]) == {"content", "collaborative", "popularity"}


def test_default_k_is_ten(client: TestClient) -> None:
    assert client.get("/students/eva/recommendations").json()["k"] == 10


def test_unknown_student_is_404(client: TestClient) -> None:
    response = client.get("/students/ninguem/recommendations")
    assert response.status_code == 404
    assert "ninguem" in response.json()["detail"]


@pytest.mark.parametrize("k", [0, 51, "abc"])
def test_invalid_k_is_422(client: TestClient, k: object) -> None:
    assert client.get("/students/ana/recommendations", params={"k": k}).status_code == 422


def test_empty_result_is_a_valid_answer(client: TestClient) -> None:
    response = client.get("/students/duda/recommendations")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_health_and_metrics(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    client.get("/students/ana/recommendations")
    metrics = client.get("/metrics").text
    assert "lr_http_requests_total" in metrics
    assert 'route="/students/{student_id}/recommendations"' in metrics
    assert "lr_recommendations_total" in metrics
