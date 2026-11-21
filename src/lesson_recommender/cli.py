"""Linha de comando: gerar dataset, carregar o grafo e rodar a avaliação offline."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from lesson_recommender.artifacts.publisher import embeddings_index, publish
from lesson_recommender.artifacts.store import (
    ArtifactStore,
    LocalArtifactStore,
    S3ArtifactStore,
    build_s3_client,
)
from lesson_recommender.config import ArtifactsBackend, Settings
from lesson_recommender.dataset.generator import GeneratorConfig, generate
from lesson_recommender.dataset.io import load_dataset, save_dataset
from lesson_recommender.domain.errors import RecommenderError
from lesson_recommender.domain.models import Dataset
from lesson_recommender.domain.ports import EmbeddingProvider
from lesson_recommender.embeddings.factory import build_embedder
from lesson_recommender.evaluation.report import render_markdown
from lesson_recommender.evaluation.runner import EvaluationConfig, evaluate
from lesson_recommender.observability import configure_logging

logger = logging.getLogger("lesson_recommender.cli")


def _generate(args: argparse.Namespace) -> None:
    dataset = generate(GeneratorConfig(seed=args.seed, students=args.students))
    save_dataset(dataset, args.output)
    logger.info(
        "dataset gerado",
        extra={
            "path": str(args.output),
            "lessons": len(dataset.lessons),
            "students": len(dataset.students),
            "bookings": len(dataset.bookings),
            "ratings": len(dataset.ratings),
        },
    )


def _load_graph(args: argparse.Namespace) -> None:
    from lesson_recommender.bootstrap import neo4j_driver
    from lesson_recommender.graph.loader import GraphLoader

    settings = Settings()
    dataset = load_dataset(args.dataset)
    with neo4j_driver(settings) as driver:
        GraphLoader(driver, database=settings.neo4j_database).load(dataset)


def _evaluate(args: argparse.Namespace) -> None:
    settings = Settings()
    embedder = build_embedder(
        settings.embeddings_backend,
        model_name=settings.embeddings_model,
        dimensions=settings.embeddings_dimensions,
    )
    config = EvaluationConfig(
        ks=tuple(args.k),
        test_fraction=args.test_fraction,
        seed=args.seed,
        neighbors=settings.neighbors,
        weights=settings.weights(),
    )
    dataset = load_dataset(args.dataset)
    report = evaluate(dataset, embedder, config, tune=args.tune)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    args.output.write_text(markdown)
    logger.info("relatório gerado", extra={"path": str(args.output)})
    if args.publish:
        _publish(settings, embedder, dataset, markdown)


def _artifact_store(settings: Settings) -> ArtifactStore:
    if settings.artifacts_backend is ArtifactsBackend.S3:
        client = build_s3_client(
            settings.s3_endpoint_url,
            settings.s3_access_key,
            settings.s3_secret_key.get_secret_value(),
            settings.s3_region,
        )
        return S3ArtifactStore(client, settings.s3_bucket)
    return LocalArtifactStore(settings.artifacts_dir)


def _publish(
    settings: Settings, embedder: EmbeddingProvider, dataset: Dataset, markdown: str
) -> None:
    index, manifest = embeddings_index(
        embedder,
        dataset.lessons,
        {m.id: m for m in dataset.modalities},
        {i.id: i for i in dataset.instructors},
    )
    published = publish(
        _artifact_store(settings),
        run_date=datetime.now(UTC).date(),
        index=index,
        manifest=manifest,
        report_markdown=markdown,
    )
    logger.info("artefatos publicados", extra=asdict(published))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lesson-recommender")
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="gera o dataset sintético")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--students", type=int, default=400)
    gen.add_argument("--output", type=Path, default=Path("data/dataset.json"))
    gen.set_defaults(handler=_generate)

    load = commands.add_parser("load-graph", help="carrega o dataset no Neo4j")
    load.add_argument("--dataset", type=Path, default=Path("data/dataset.json"))
    load.set_defaults(handler=_load_graph)

    ev = commands.add_parser("evaluate", help="avaliação offline e relatório Markdown")
    ev.add_argument("--dataset", type=Path, default=Path("data/dataset.json"))
    ev.add_argument("--output", type=Path, default=Path("reports/avaliacao.md"))
    ev.add_argument("--k", type=int, nargs="+", default=[5, 10])
    ev.add_argument("--test-fraction", type=float, default=0.2)
    ev.add_argument("--seed", type=int, default=42)
    ev.add_argument(
        "--tune",
        action="store_true",
        help="escolhe os pesos do híbrido num recorte de validação (sem usar o teste)",
    )
    ev.add_argument(
        "--publish",
        action="store_true",
        help="publica relatório e índice de embeddings no artifact store (LR_ARTIFACTS_*)",
    )
    ev.set_defaults(handler=_evaluate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(Settings().log_level)
    try:
        args.handler(args)
    except (FileNotFoundError, ValueError, RecommenderError) as error:
        logger.error("falha no comando", extra={"command": args.command, "error": str(error)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
