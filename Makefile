.PHONY: help install lint typecheck test test-unit test-integration dataset evaluate run \
	network up up-all down logs ps seed clean

PYTHON ?= .venv/bin/python
COMPOSE ?= docker compose
ALL_PROFILES := --profile core --profile observability
# Docker Desktop no macOS não monta o socket do usuário no container do Ryuk (testcontainers).
ifeq ($(shell uname),Darwin)
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE ?= /var/run/docker.sock
endif

help: ## Lista os alvos
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install: ## Cria o venv e instala dependências de desenvolvimento
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

lint: ## ruff (lint + formato)
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

typecheck: ## mypy estrito
	$(PYTHON) -m mypy

test: ## Todos os testes (integração pula sem Docker)
	$(PYTHON) -m pytest

test-unit: ## Só testes de unidade
	$(PYTHON) -m pytest tests/unit

test-integration: ## Só integração com Neo4j (testcontainers)
	$(PYTHON) -m pytest tests/integration

dataset: ## Gera data/dataset.json (seed 42)
	$(PYTHON) -m lesson_recommender.cli generate --output data/dataset.json

evaluate: dataset ## Avaliação offline: regenera reports/avaliacao.md
	$(PYTHON) -m lesson_recommender.cli evaluate --dataset data/dataset.json --output reports/avaliacao.md

run: dataset ## API local com repositório em memória
	$(PYTHON) -m uvicorn --factory lesson_recommender.bootstrap:create_production_app --port 8000

network: ## Cria a rede compartilhada portfolio-net (opcional)
	docker network inspect portfolio-net >/dev/null 2>&1 || docker network create portfolio-net

up: ## Sobe o núcleo (Neo4j, MinIO, carga, API)
	$(COMPOSE) --profile core up --build -d

up-all: ## Núcleo + observabilidade (Jaeger, Prometheus)
	LR_OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318 $(COMPOSE) $(ALL_PROFILES) up --build -d

down: ## Para os containers (mantém volumes)
	$(COMPOSE) $(ALL_PROFILES) down

logs: ## Acompanha os logs
	$(COMPOSE) $(ALL_PROFILES) logs -f

ps: ## Estado dos serviços
	$(COMPOSE) $(ALL_PROFILES) ps -a

seed: ## Regera o dataset, recarrega o grafo e publica artefatos no MinIO
	$(COMPOSE) --profile core run --rm seed

clean: ## Remove containers, volumes e arquivos gerados
	$(COMPOSE) $(ALL_PROFILES) down -v
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('data', 'artifacts', '.pytest_cache', '.mypy_cache', '.ruff_cache')]"
