# CLAUDE.md

Guia para sessões de agente neste repositório.

## Visão

Recomendador híbrido de aulas (yoga e pilates) para o SaaS fictício de estúdios. O **núcleo é a
avaliação offline**: toda mudança no recomendador precisa ser medida pelo relatório
`reports/avaliacao.md`, contra os baselines de popularidade e aleatório.

## Regras

- Domínio 100% fictício. Nenhum nome real de pessoa ou empresa; e-mails só `@example.com`.
- Nenhum segredo real. Valores de desenvolvimento são `dev-only-*`. Nunca leia nem commite
  `.env`, `data/` ou `config.local.yaml`.
- Docs em português do Brasil; identificadores de código em inglês.
- Testes nunca acessam a internet. A integração usa só testcontainers (Neo4j local).
- Arquitetura hexagonal: `domain/` e `recommender/` não importam `neo4j`, `fastapi`, `boto3`
  nem `sentence_transformers`. Adaptadores ficam em `adapters/`, `graph/`, `embeddings/`,
  `artifacts/` e `api/`; a composição fica em `bootstrap.py`.
- Regras de negócio (nível, contraindicação, lotação) são filtros duros em `domain/rules.py`.
  Nunca as transforme em penalidade de pontuação.
- O colaborativo existe em duas implementações (Python e Cypher), e elas precisam concordar.
  Mudou uma, mude a outra e rode `make test-integration`.
- Determinismo: seeds fixas, desempate explícito por id, hashing com `blake2b`. Não use
  `hash()` nem iteração sobre `set` para ordenar resultados.
- Se a mudança altera números da avaliação, rode `make evaluate` e commite o relatório. O CI
  falha se ele divergir.
- Decisão de arquitetura nova vira ADR em `docs/adr/` (Contexto / Decisão / Consequências /
  Alternativas).
- Commits em Conventional Commits, mensagem via arquivo (`git commit -F`).

## Comandos

```bash
make install           # venv + deps de dev
make lint typecheck    # ruff + mypy estrito
make test-unit         # rápido, sem Docker
make test-integration  # Neo4j via testcontainers
make evaluate          # dataset + relatório de avaliação
make run               # API local (memória)
make up | up-all | ps | logs | seed | down | clean   # docker-compose (perfis core/observability)
```

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `src/lesson_recommender/domain/` | Entidades imutáveis, regras, portas, erros |
| `src/lesson_recommender/recommender/` | Conteúdo, colaborativo de referência, candidatas, híbrido, explicações |
| `src/lesson_recommender/evaluation/` | Split temporal, métricas, baselines, runner, relatório |
| `src/lesson_recommender/graph/` | Cypher, carga, repositório Neo4j |
| `src/lesson_recommender/artifacts/` | Porta de storage (local, S3/MinIO) e publicação por data |
| `tests/factories.py` | Estúdio mínimo, com um caso por regra |
| `docs/` | design doc, ADRs, roteiro do núcleo |

## Fluxo de trabalho

1. Leia o design doc e o ADR relacionado antes de mudar comportamento.
2. Escreva o teste primeiro (métricas e regras têm casos calculados à mão).
3. Implemente; rode `make lint typecheck test`.
4. Se o ranqueamento mudou, rode `make evaluate` e compare o diff do relatório.
5. Atualize docs e ADRs; abra o PR com o template (inclui o antes e depois das métricas).

## Ambiente local (macOS)

O Makefile exporta `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` no Darwin.
Sem isso, o Ryuk do testcontainers falha no Docker Desktop. Se as portas padrão estiverem
ocupadas, ajuste `LR_*_PORT` no `.env`.
