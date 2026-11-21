# 0001. Arquitetura hexagonal com portas para repositório, colaborativo e embeddings

- Status: aceito
- Data: 2026-11-21

## Contexto

O recomendador precisa rodar em três situações bem diferentes:

1. na API, lendo o grafo de produção no Neo4j;
2. na avaliação offline, que precisa de um recorte de treino (só o passado) e roda centenas de
   consultas por segundo;
3. nos testes, que têm de ser rápidos, determinísticos e sem infraestrutura.

Se o algoritmo chamasse o driver do Neo4j direto, a avaliação offline precisaria carregar um
grafo por experimento, e os testes de unidade dependeriam de Docker.

## Decisão

O núcleo (`domain/` e `recommender/`) só conhece portas, definidas em `domain/ports.py`:

- `CatalogRepository`: aluno, catálogo, modalidades, instrutores, histórico e popularidade;
- `CollaborativeSource`: sinal colaborativo por vizinhança;
- `EmbeddingProvider`: textos para vetores normalizados.

Os adaptadores ficam na borda:

- `adapters/memory_repository.py` implementa catálogo e colaborativo em memória;
- `graph/repository.py` implementa as mesmas portas com Cypher;
- `embeddings/` traz as duas implementações de embeddings.

A composição acontece num único lugar (`bootstrap.py`), escolhida por variável de ambiente.

## Consequências

- A lógica pura é testável com o repositório em memória, sem Docker.
- A avaliação offline usa o mesmo `HybridRecommender` da API, só com outro adaptador. O que é
  medido é o que vai para produção.
- Duas implementações do colaborativo precisam continuar equivalentes. Um teste de integração
  compara Cypher e memória aluno a aluno (ADR 0003).
- Há uma camada a mais de indireção, aceitável pelo tamanho do projeto.

## Alternativas consideradas

- **Chamar o Neo4j direto do recomendador:** é mais simples, mas acopla a avaliação e os testes
  ao banco.
- **Mock do driver nos testes:** testa a chamada, não o comportamento. Também não resolve a
  avaliação offline.
