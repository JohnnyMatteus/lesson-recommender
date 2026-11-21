import importlib.util

import numpy as np
import pytest

from lesson_recommender.domain.errors import ConfigurationError
from lesson_recommender.embeddings.factory import build_embedder
from lesson_recommender.embeddings.hashing import HashingEmbedder, normalize_text, tokenize


def test_same_text_gives_same_vector_across_instances() -> None:
    text = "Hatha Yoga com respiração consciente"
    first = HashingEmbedder(256).embed([text])
    second = HashingEmbedder(256).embed([text])
    np.testing.assert_array_equal(first, second)


def test_vectors_are_unit_norm_and_empty_text_is_zero() -> None:
    vectors = HashingEmbedder(128).embed(["alongamento profundo", ""])
    assert np.linalg.norm(vectors[0]) == pytest.approx(1.0)
    assert not vectors[1].any()


def test_related_texts_are_closer_than_unrelated() -> None:
    embedder = HashingEmbedder(1024)
    query, near, far = embedder.embed(
        [
            "alongamento e flexibilidade de quadril",
            "aula de alongamento profundo para flexibilidade",
            "fortalecimento do core com molas no reformer",
        ]
    )
    assert float(query @ near) > float(query @ far)


def test_accents_and_case_are_ignored() -> None:
    assert normalize_text("Respiração") == "respiracao"
    assert tokenize("A Respiração e o Relaxamento") == ["respiracao", "relaxamento"]


def test_dimensions_must_be_positive() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        HashingEmbedder(0)


def test_factory_builds_hashing_by_default() -> None:
    embedder = build_embedder("hashing", model_name="ignorado", dimensions=64)
    assert embedder.name == "hashing-64"


def test_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ConfigurationError, match="inválido"):
        build_embedder("word2vec", model_name="x", dimensions=64)


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is not None,
    reason="sentence-transformers instalado: o erro de dependência ausente não se aplica",
)
def test_factory_explains_missing_optional_dependency() -> None:
    with pytest.raises(ConfigurationError, match="extra"):
        build_embedder("sentence-transformers", model_name="x", dimensions=64)
