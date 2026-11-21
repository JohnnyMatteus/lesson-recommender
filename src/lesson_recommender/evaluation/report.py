"""Renderiza o relatório de avaliação em Markdown (determinístico: sem data de geração)."""

from __future__ import annotations

from lesson_recommender.evaluation.runner import EvaluationReport


def _pct(value: float) -> str:
    return f"{value:.3f}"


def render_markdown(report: EvaluationReport) -> str:
    config = report.config
    lines = [
        "# Relatório de avaliação offline",
        "",
        "> Gerado por `lesson-recommender evaluate`. Não edite à mão: rode o comando de novo.",
        "",
        "## Protocolo",
        "",
        f"- Split temporal global: corte em `{report.cutoff.isoformat()}` "
        f"({int(config.test_fraction * 100)}% das reservas mais recentes no teste).",
        f"- Reservas de treino: {report.train_bookings}; "
        f"reservas de teste: {report.test_bookings}.",
        f"- Relevantes: aulas reservadas pela primeira vez após o corte "
        f"({report.relevant_items} pares aluno-aula).",
        f"- Alunos avaliados: {report.students_evaluated} de {report.students_total} "
        "(os demais não têm treino ou não descobriram aulas no teste).",
        f"- Catálogo: {report.catalog_size} aulas. Embeddings: `{report.embedder}`. "
        f"Vizinhos: {config.neighbors}. Seed: {config.seed}.",
        "- Candidatas: aulas não reservadas no treino que passam nas regras de nível e "
        "contraindicação (lotação desligada, ver roteiro).",
        "",
    ]
    for k in config.ks:
        lines += [
            f"## Resultados com k = {k}",
            "",
            f"| Modelo | Precision@{k} | Recall@{k} | NDCG@{k} | MAP@{k} | Cobertura |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        best = max(result.metrics[k].ndcg for result in report.results)
        for result in report.results:
            m = result.metrics[k]
            name = f"**{result.name}**" if m.ndcg == best else result.name
            lines.append(
                f"| {name} | {_pct(m.precision)} | {_pct(m.recall)} | {_pct(m.ndcg)} | "
                f"{_pct(m.map)} | {_pct(m.coverage)} |"
            )
        lines.append("")

    lines += [
        "## Híbrido contra baselines (NDCG, bootstrap pareado)",
        "",
        f"Diferença média por aluno e intervalo de 95% com {config.bootstrap_samples} "
        "reamostragens.",
        "",
        "| Baseline | k | Δ NDCG | IC 95% | Conclusão |",
        "|---|---:|---:|---|---|",
    ]
    for interval in report.intervals:
        verdict = (
            "híbrido melhor"
            if interval.low > 0
            else "baseline melhor"
            if interval.high < 0
            else "sem diferença clara"
        )
        lines.append(
            f"| {interval.baseline} | {interval.k} | {interval.mean_delta:+.3f} | "
            f"[{interval.low:+.3f}, {interval.high:+.3f}] | {verdict} |"
        )
    lines += ["", "## Modelos", ""]
    lines += [f"- `{result.name}`: {result.description}." for result in report.results]
    return "\n".join(lines) + "\n"
