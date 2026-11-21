"""Integração com Neo4j real (testcontainers). Pula quando não há Docker disponível.

O teste central compara o colaborativo calculado em Cypher com a implementação de referência
em memória, sobre o mesmo dataset: as duas precisam concordar aula a aula.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from neo4j import Driver

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.dataset.generator import GeneratorConfig, generate
from lesson_recommender.domain.models import Dataset
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.graph.loader import GraphLoader
from lesson_recommender.graph.repository import Neo4jRepository
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender
from tests.factories import studio

pytestmark = pytest.mark.integration

NEO4J_IMAGE = "neo4j:5.26-community"


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def driver() -> Iterator[Driver]:
    if not _docker_available():
        pytest.skip("Docker indisponível: teste de integração com Neo4j pulado")
    from testcontainers.community.neo4j import Neo4jContainer

    with (
        Neo4jContainer(NEO4J_IMAGE, password="dev-only-change-me") as container,
        container.get_driver() as neo4j_driver,
    ):
        yield neo4j_driver


@pytest.fixture(scope="module")
def generated() -> Dataset:
    return generate(GeneratorConfig(seed=3, lessons=30, students=60, weeks=10))


def test_loads_studio_and_reads_it_back(driver: Driver) -> None:
    dataset = studio()
    summary = GraphLoader(driver).load(dataset)
    assert summary.booking_edges == 5
    repo = Neo4jRepository(driver)
    memory = InMemoryRepository(dataset)
    assert list(repo.list_lessons()) == list(memory.list_lessons())
    assert repo.get_student("duda") == memory.get_student("duda")
    assert repo.get_student("ninguem") is None
    assert repo.history("ana") == memory.history("ana")
    assert dict(repo.popularity()) == dict(memory.popularity())
    assert dict(repo.modalities()) == dict(memory.modalities())


def test_loader_is_idempotent(driver: Driver) -> None:
    loader = GraphLoader(driver)
    loader.load(studio())
    loader.load(studio())
    records, _, _ = driver.execute_query("MATCH ()-[r:RESERVOU]->() RETURN count(r) AS n")
    assert records[0]["n"] == 5


def test_cypher_collaborative_matches_reference(driver: Driver, generated: Dataset) -> None:
    GraphLoader(driver, batch_size=100).load(generated)
    graph = Neo4jRepository(driver)
    memory = InMemoryRepository(generated)
    for student in generated.students[:25]:
        expected = memory.neighbor_scores(student.id, neighbors=10)
        actual = graph.neighbor_scores(student.id, neighbors=10)
        assert set(actual) == set(expected), student.id
        for lesson_id, signal in expected.items():
            assert actual[lesson_id].score == pytest.approx(signal.score), (student.id, lesson_id)
            assert actual[lesson_id].support == signal.support


def test_hybrid_over_graph_matches_memory(driver: Driver, generated: Dataset) -> None:
    GraphLoader(driver).load(generated)
    embedder = HashingEmbedder(256)

    def build(repo: InMemoryRepository | Neo4jRepository) -> HybridRecommender:
        content = ContentModel(embedder, repo.list_lessons(), repo.modalities(), repo.instructors())
        return HybridRecommender(repo, repo, content, neighbors=10)

    graph, memory = build(Neo4jRepository(driver)), build(InMemoryRepository(generated))
    for student in generated.students[:10]:
        assert graph.rank(student.id, 5) == memory.rank(student.id, 5)
