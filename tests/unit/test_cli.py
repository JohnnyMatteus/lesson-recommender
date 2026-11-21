from pathlib import Path

import pytest

from lesson_recommender.cli import main


def test_generate_then_evaluate(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    report = tmp_path / "relatorio.md"
    assert main(["generate", "--students", "80", "--output", str(dataset)]) == 0
    assert dataset.exists()
    assert main(["evaluate", "--dataset", str(dataset), "--output", str(report), "--k", "5"]) == 0
    assert "Precision@5" in report.read_text()


def test_missing_dataset_fails_with_exit_code(tmp_path: Path) -> None:
    assert main(["evaluate", "--dataset", str(tmp_path / "nao-existe.json")]) == 1


def test_unknown_command_exits() -> None:
    with pytest.raises(SystemExit):
        main(["treinar"])


def test_evaluate_publishes_artifacts_to_local_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LR_ARTIFACTS_BACKEND", "local")
    monkeypatch.setenv("LR_ARTIFACTS_DIR", str(tmp_path / "artefatos"))
    dataset = tmp_path / "dataset.json"
    assert main(["generate", "--students", "60", "--output", str(dataset)]) == 0
    args = ["evaluate", "--dataset", str(dataset), "--output", str(tmp_path / "r.md")]
    assert main([*args, "--publish"]) == 0
    published = list((tmp_path / "artefatos" / "runs").glob("*/avaliacao.md"))
    assert len(published) == 1
    assert (published[0].parent / "embeddings" / "lessons.npy").exists()
