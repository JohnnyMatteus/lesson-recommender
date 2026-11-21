# Relatório de avaliação offline

> Gerado por `lesson-recommender evaluate`. Não edite à mão: rode o comando de novo.

## Protocolo

- Split temporal global: corte em `2026-08-04T08:00:00+00:00` (20% das reservas mais recentes no teste).
- Reservas de treino: 12279; reservas de teste: 3075.
- Relevantes: aulas reservadas pela primeira vez após o corte (258 pares aluno-aula).
- Alunos avaliados: 201 de 400 (os demais não têm treino ou não descobriram aulas no teste).
- Catálogo: 80 aulas. Embeddings: `hashing-1024`. Vizinhos: 30. Seed: 42.
- Candidatas: aulas não reservadas no treino que passam nas regras de nível e contraindicação (lotação desligada, ver roteiro).

## Resultados com k = 5

| Modelo | Precision@5 | Recall@5 | NDCG@5 | MAP@5 | Cobertura |
|---|---:|---:|---:|---:|---:|
| aleatorio | 0.033 | 0.133 | 0.075 | 0.050 | 1.000 |
| popularidade | 0.047 | 0.178 | 0.125 | 0.097 | 0.200 |
| conteudo | 0.103 | 0.413 | 0.298 | 0.244 | 1.000 |
| colaborativo | 0.108 | 0.436 | 0.320 | 0.269 | 0.938 |
| **hibrido** | 0.121 | 0.485 | 0.343 | 0.283 | 0.963 |

## Resultados com k = 10

| Modelo | Precision@10 | Recall@10 | NDCG@10 | MAP@10 | Cobertura |
|---|---:|---:|---:|---:|---:|
| aleatorio | 0.036 | 0.289 | 0.127 | 0.070 | 1.000 |
| popularidade | 0.044 | 0.344 | 0.180 | 0.119 | 0.388 |
| conteudo | 0.075 | 0.610 | 0.364 | 0.273 | 1.000 |
| colaborativo | 0.076 | 0.599 | 0.378 | 0.295 | 0.975 |
| **hibrido** | 0.083 | 0.663 | 0.404 | 0.309 | 1.000 |

## Híbrido contra baselines (NDCG, bootstrap pareado)

Diferença média por aluno e intervalo de 95% com 1000 reamostragens.

| Baseline | k | Δ NDCG | IC 95% | Conclusão |
|---|---:|---:|---|---|
| popularidade | 5 | +0.218 | [+0.166, +0.269] | híbrido melhor |
| popularidade | 10 | +0.224 | [+0.180, +0.270] | híbrido melhor |
| aleatorio | 5 | +0.269 | [+0.212, +0.329] | híbrido melhor |
| aleatorio | 10 | +0.277 | [+0.228, +0.333] | híbrido melhor |

## Ajuste de pesos (recorte de validação)

Os pesos do híbrido foram escolhidos num recorte de validação tirado do treino, sem tocar no teste: corte interno em `2026-07-13T09:30:00+00:00` (9813 reservas de treino, 2466 de validação, 189 alunos). Grade com passo 0.1 e soma 1; critério: NDCG@10.

| Posição | Conteúdo | Colaborativo | Popularidade | NDCG@10 |
|---:|---:|---:|---:|---:|
| 1 | 0.3 | 0.6 | 0.1 | 0.367 |
| 2 | 0.2 | 0.7 | 0.1 | 0.365 |
| 3 | 0.3 | 0.7 | 0.0 | 0.365 |
| 4 | 0.5 | 0.4 | 0.1 | 0.363 |
| 5 | 0.4 | 0.4 | 0.2 | 0.362 |

Pior combinação da grade: NDCG@10 = 0.150 (66 combinações testadas).

## Modelos

- `aleatorio`: Ordem aleatória entre as elegíveis.
- `popularidade`: Mais alunos distintos no treino.
- `conteudo`: Só embeddings (ablação).
- `colaborativo`: Só vizinhança de alunos, mesma conta do Cypher (ablação).
- `hibrido`: Conteúdo 0.3 + colaborativo 0.6 + popularidade 0.1.
