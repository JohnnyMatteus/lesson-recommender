import pytest

from lesson_recommender.dataset.generator import GeneratorConfig, generate
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.evaluation.runner import EVALUATION_POLICY, EvaluationConfig, evaluate
from lesson_recommender.evaluation.split import temporal_split
from lesson_recommender.evaluation.tuning import tune_weights, weight_grid


def test_grid_sums_to_one_and_has_no_duplicates() -> None:
    grid = weight_grid(0.25)
    assert len(grid) == 15
    assert len({(w.content, w.collaborative, w.popularity) for w in grid}) == 15
    assert all(w.content + w.collaborative + w.popularity == pytest.approx(1.0) for w in grid)


def test_grid_step_must_divide_one() -> None:
    with pytest.raises(ValueError, match="step"):
        weight_grid(0.3)


def test_tuning_uses_only_the_training_cut() -> None:
    dataset = generate(GeneratorConfig(seed=3, lessons=40, students=120, weeks=16))
    outer = temporal_split(dataset)
    result = tune_weights(
        outer.train, HashingEmbedder(256), policy=EVALUATION_POLICY, k=10, step=0.25
    )
    assert result.cutoff < outer.cutoff
    assert result.train_bookings + result.validation_bookings == len(outer.train.bookings)
    scores = [trial.ndcg for trial in result.trials]
    assert scores == sorted(scores, reverse=True)
    assert result.best == result.trials[0].weights


def test_evaluate_with_tune_reports_the_chosen_weights() -> None:
    dataset = generate(GeneratorConfig(seed=3, lessons=40, students=120, weeks=16))
    report = evaluate(
        dataset, HashingEmbedder(256), EvaluationConfig(ks=(10,), bootstrap_samples=50), tune=True
    )
    assert report.tuning is not None
    assert report.config.weights == report.tuning.best
