import pytest

from lesson_recommender.dataset.generator import GeneratorConfig, generate
from lesson_recommender.embeddings.hashing import HashingEmbedder
from lesson_recommender.evaluation.report import render_markdown
from lesson_recommender.evaluation.runner import (
    EvaluationConfig,
    EvaluationReport,
    evaluate,
    paired_bootstrap,
)

CONFIG = EvaluationConfig(ks=(5, 10), bootstrap_samples=200)


@pytest.fixture(scope="module")
def report() -> EvaluationReport:
    dataset = generate(GeneratorConfig(seed=11, lessons=50, students=200, weeks=20))
    return evaluate(dataset, HashingEmbedder(512), CONFIG)


def metric(report: EvaluationReport, model: str, k: int) -> float:
    return next(r for r in report.results if r.name == model).metrics[k].ndcg


def test_all_models_are_evaluated_on_the_same_students(report: EvaluationReport) -> None:
    names = [result.name for result in report.results]
    assert names == ["aleatorio", "popularidade", "conteudo", "colaborativo", "hibrido"]
    sizes = {len(result.per_user_ndcg[10]) for result in report.results}
    assert sizes == {report.students_evaluated}


def test_planted_signal_lets_hybrid_beat_baselines(report: EvaluationReport) -> None:
    for k in CONFIG.ks:
        assert metric(report, "hibrido", k) > metric(report, "popularidade", k)
        assert metric(report, "hibrido", k) > metric(report, "aleatorio", k)


def test_hybrid_vs_popularity_interval_is_positive(report: EvaluationReport) -> None:
    interval = next(i for i in report.intervals if i.baseline == "popularidade" and i.k == 10)
    assert interval.low > 0


def test_metrics_are_bounded(report: EvaluationReport) -> None:
    for result in report.results:
        for values in result.metrics.values():
            for value in (
                values.precision,
                values.recall,
                values.ndcg,
                values.map,
                values.coverage,
            ):
                assert 0.0 <= value <= 1.0


def test_popularity_has_lower_coverage_than_random(report: EvaluationReport) -> None:
    by_name = {result.name: result for result in report.results}
    assert by_name["popularidade"].metrics[10].coverage < by_name["aleatorio"].metrics[10].coverage


def test_report_is_deterministic_and_complete(report: EvaluationReport) -> None:
    dataset = generate(GeneratorConfig(seed=11, lessons=50, students=200, weeks=20))
    again = evaluate(dataset, HashingEmbedder(512), CONFIG)
    markdown = render_markdown(report)
    assert markdown == render_markdown(again)
    for section in ("## Protocolo", "## Resultados com k = 5", "NDCG@10", "bootstrap pareado"):
        assert section in markdown


def test_paired_bootstrap_by_hand() -> None:
    delta, low, high = paired_bootstrap([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], samples=50, seed=1)
    assert (delta, low, high) == (1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="mesmo tamanho"):
        paired_bootstrap([1.0], [], samples=10, seed=1)


def test_invalid_ks() -> None:
    with pytest.raises(ValueError, match="ks"):
        EvaluationConfig(ks=(0,))
