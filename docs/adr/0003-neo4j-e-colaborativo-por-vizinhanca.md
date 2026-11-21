# 0003. Neo4j para o grafo de interações e colaborativo por vizinhança em Cypher

- Status: aceito
- Data: 2026-11-21

## Contexto

O sinal colaborativo vem de "alunos que frequentam as mesmas aulas que você também frequentam
estas outras". É uma travessia de dois saltos, Aluno → Aula → Aluno → Aula, que num banco
relacional vira autojunções caras e difíceis de ler. O domínio já é um grafo: alunos,
aulas, instrutores e modalidades.

## Decisão

- Modelar no Neo4j:
  - os nós `Aluno`, `Aula`, `Instrutor` e `Modalidade`;
  - as relações `RESERVOU`, `AVALIOU`, `MINISTRA` e `É_DE`.
- `RESERVOU` e `AVALIOU` são agregadas: uma aresta por par aluno-aula.
  - `RESERVOU` guarda `count`, `first_at` e `last_at`.
  - `AVALIOU` guarda só a nota mais recente.

  Isso mantém a contagem de vizinhos correta (`count(*)` = aulas em comum) e o grafo pequeno.
- Colaborativo user-based com similaridade de Jaccard:
  - mantém os N vizinhos mais próximos, com desempate pelo id do aluno;
  - pontua cada aula com `sim × nota/5`, ou `sim × 0,6` quando o vizinho só reservou.

  A consulta está em `graph/cypher.py::COLLABORATIVE_NEIGHBORHOOD`.
- A mesma conta existe em Python (`recommender/collaborative.py`), que é a **especificação
  de referência**. O teste de integração com testcontainers carrega um dataset gerado e exige
  que as duas implementações concordem em todas as aulas, scores e contagens de suporte.
- Carga idempotente com `MERGE` em lotes (`UNWIND`) e constraints de unicidade por `id`.

## Consequências

- A consulta Cypher é legível e explicável numa entrevista.
- A avaliação offline usa a implementação em memória, que gera o mesmo resultado sem carregar
  um grafo por recorte de treino.
- O teste de paridade protege contra divergência silenciosa entre as duas implementações.
- Para catálogos grandes, a consulta online por aluno pode ficar cara (vizinhos de vizinhos).
  O plano de evolução prevê pré-computar similaridades com o GDS (Node Similarity) em lote.

## Alternativas consideradas

- **Fatoração de matrizes (ALS):** costuma ser melhor com muitos dados, mas é opaca para
  explicar ("por que esta aula?") e exige treino periódico. Fica como próximo passo, comparado
  pelo mesmo relatório.
- **Item-based kNN:** catálogo pequeno (dezenas de aulas) e muitos alunos tornam o user-based
  mais informativo aqui. É fácil de trocar atrás da mesma porta.
- **PostgreSQL com autojunções:** funciona, mas é menos expressivo para a travessia. Também
  deixaria de exercitar a unidade de grafos do curso.
