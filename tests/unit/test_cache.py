import fakeredis
import pytest
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from lesson_recommender.adapters.memory_repository import InMemoryRepository
from lesson_recommender.adapters.redis_cache import RedisRecommendationCache, cache_key
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.recommender.cached import CachedRecommender
from lesson_recommender.recommender.content import ContentModel
from lesson_recommender.recommender.hybrid import HybridRecommender, Recommendation, Weights
from tests.factories import studio


class CountingRecommender:
    def __init__(self, inner: HybridRecommender) -> None:
        self.inner = inner
        self.calls = 0

    @property
    def weights(self) -> Weights:
        return self.inner.weights

    def recommend(self, student_id: str, k: int) -> list[Recommendation]:
        self.calls += 1
        return self.inner.recommend(student_id, k)


@pytest.fixture
def hybrid() -> HybridRecommender:
    repo = InMemoryRepository(studio())
    content = ContentModel(
        HashingEmbedder(256), repo.list_lessons(), repo.modalities(), repo.instructors()
    )
    return HybridRecommender(repo, repo, content, neighbors=10)


@pytest.fixture
def client() -> Redis:
    return fakeredis.FakeRedis()


def test_second_call_is_served_from_cache(hybrid: HybridRecommender, client: Redis) -> None:
    counting = CountingRecommender(hybrid)
    cached = CachedRecommender(counting, RedisRecommendationCache(client, ttl_seconds=60))

    first = cached.recommend("eva", 3)
    second = cached.recommend("eva", 3)

    assert counting.calls == 1
    assert second == first
    assert cached.weights == hybrid.weights


def test_entry_has_ttl_that_new_writes_do_not_extend(
    hybrid: HybridRecommender, client: Redis
) -> None:
    cache = RedisRecommendationCache(client, ttl_seconds=60)
    cached = CachedRecommender(hybrid, cache)
    cached.recommend("eva", 3)
    client.expire(cache_key("eva"), 10)

    cached.recommend("eva", 5)

    assert set(client.hkeys(cache_key("eva"))) == {b"3", b"5"}
    assert 0 < client.ttl(cache_key("eva")) <= 10


def test_invalidate_removes_every_k_of_the_student(
    hybrid: HybridRecommender, client: Redis
) -> None:
    cache = RedisRecommendationCache(client, ttl_seconds=60)
    cached = CachedRecommender(hybrid, cache)
    cached.recommend("eva", 3)
    cached.recommend("ana", 3)

    cache.invalidate("eva")

    assert not client.exists(cache_key("eva"))
    assert client.exists(cache_key("ana"))


def test_redis_down_degrades_to_no_cache(hybrid: HybridRecommender) -> None:
    server = fakeredis.FakeServer()
    server.connected = False
    broken = fakeredis.FakeRedis(server=server)
    cached = CachedRecommender(hybrid, RedisRecommendationCache(broken, ttl_seconds=60))

    assert cached.recommend("eva", 3) == hybrid.recommend("eva", 3)
    with pytest.raises(RedisConnectionError):
        broken.ping()


def test_ttl_must_be_positive(client: Redis) -> None:
    with pytest.raises(ValueError, match="ttl"):
        RedisRecommendationCache(client, ttl_seconds=0)
