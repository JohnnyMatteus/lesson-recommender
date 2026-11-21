# Roteiro: métrica de avaliação do modelo

Este roteiro serve para defender numa entrevista o núcleo do projeto: **como sabemos se o
recomendador é bom**. Ele cobre:

- o protocolo;
- cada métrica e por que ela está ali;
- os baselines e o intervalo de confiança;
- os trade-offs e as perguntas mais prováveis, com respostas.

Código: `src/lesson_recommender/evaluation/`. Testes com contas feitas à mão:
`tests/unit/test_metrics.py`. Relatório gerado: [`reports/avaliacao.md`](../../reports/avaliacao.md).
Decisão: [ADR 0004](../adr/0004-protocolo-de-avaliacao-offline.md).

## 1. A pergunta de negócio

O estúdio quer que alunos **descubram** aulas novas que combinem com eles. Isso aumenta a
frequência e reduz o churn. A pergunta offline correspondente:

> Dado o que sabíamos de um aluno até a data D, as aulas que ele passou a frequentar depois de D
> aparecem no topo da nossa lista?

Toda a avaliação deriva dessa frase:

- "até a data D" pede um split temporal;
- "passou a frequentar" pede que o relevante seja a primeira reserva;
- "no topo da lista" pede métricas de ranqueamento top-k.

## 2. Protocolo, passo a passo

1. **Corte temporal global.** Ordenamos todas as reservas e cortamos no quantil 80%. Treino é
   tudo antes do corte (reservas e avaliações); teste é tudo depois. O corte é o mesmo para
   todos os alunos.
2. **Relevantes.** Para cada aluno, são as aulas reservadas pela primeira vez depois do corte.
   Repetir a aula de toda terça não conta: recomendar o que o aluno já faz não gera valor.
3. **Quem é avaliado.** Alunos com histórico no treino e ao menos uma descoberta no teste. No
   relatório atual são 201 de 400. Cold start é outro problema, com outro protocolo.
4. **Candidatas.** São as aulas que o aluno não reservou no treino e que passam nas regras de
   nível e contraindicação. Todos os modelos ranqueiam exatamente esse conjunto.
5. **Ranqueamento.** Cada modelo devolve as top-k candidatas, com k = 5 e 10. Cinco é o que cabe
   num card do app; dez, uma tela de "ver mais".
6. **Métricas por aluno, depois média** (macro): cada aluno pesa igual.

### Por que desligar a regra de lotação na avaliação?

A ocupação (`booked_seats`) é uma fotografia de hoje. Em março ninguém sabia que a aula de
terça 7h estaria lotada em novembro. Aplicar a regra no passado puniria o modelo por um estado
que ele não poderia conhecer, e também privilegiaria aulas pouco procuradas. Nível e
contraindicação são atributos estáveis do aluno e da aula, então valem sempre.

## 3. As métricas

Notação: `rec` é a lista ordenada, `rel` o conjunto de relevantes e `k` o corte.

| Métrica | Fórmula | Pergunta que responde | Limitação |
|---|---|---|---|
| Precision@k | acertos no top-k / k | Quanto da lista é útil? | Ignora a ordem dentro do top-k; com poucos relevantes, o teto fica baixo |
| Recall@k | acertos no top-k / \|rel\| | Quanto do que o aluno quis nós mostramos? | Ignora a ordem; cresce com k |
| NDCG@k | DCG / IDCG, DCG = Σ 1/log2(pos+1) | Os acertos estão no alto? | Relevância binária aqui; não usa a nota |
| MAP@k | média de AP@k; AP = Σ P@i·rel(i) / min(\|rel\|, k) | Precisão acumulada a cada acerto | Pune muito o primeiro acerto tardio |
| Cobertura | itens distintos em algum top-k / catálogo | O modelo usa o catálogo todo ou só o hit? | Não diz nada de relevância |

**Métrica principal: NDCG@10.** É sensível à posição, com desconto suave, e normalizada entre 0
e 1 por aluno, o que permite comparar alunos com quantidades diferentes de relevantes. As
outras métricas são diagnósticas.

### Exemplo calculado à mão (o mesmo dos testes)

`rec = [a, b, c, d, e]`, `rel = {a, c, f}`, k = 5:

- Precision@5 = 2/5 = **0,40**
- Recall@5 = 2/3 = **0,667**, porque f não foi recomendado
- AP@5 = (1/1 + 2/3) / min(3, 5) = **0,556**
- DCG@5 = 1/log2(2) + 1/log2(4) = 1 + 0,5 = 1,5
- IDCG@5 = 1 + 1/log2(3) + 1/log2(4) = 2,131, então NDCG@5 = **0,704**

### Convenções que costumam gerar discussão

- **Lista menor que k:** precision divide por k mesmo assim. Uma lista curta é penalizada,
  porque o espaço vazio na tela é custo de oportunidade.
- **AP normalizado por min(|rel|, k):** se o aluno tem 4 relevantes e k = 2, acertar as duas
  posições vale 1, não 0,5. Sem isso, o máximo atingível dependeria do aluno.
- **Itens repetidos na lista** levantam erro em vez de serem tolerados: um bug no modelo não
  pode inflar a métrica.
- **Recall, AP e NDCG sem relevantes** levantam erro. O protocolo exclui esses alunos antes;
  dividir por zero em silêncio esconderia um bug.

## 4. Baselines e ablações

| Modelo | Por que existe |
|---|---|
| Aleatório (seed por aluno) | Piso: o que qualquer modelo deveria superar. Mostra o tamanho do conjunto de candidatas |
| Popularidade | Baseline forte e honesto em recomendação. Se não o vencemos, a complexidade não se paga |
| Só conteúdo | Ablação: quanto vem dos embeddings |
| Só colaborativo | Ablação: quanto vem do grafo |
| Híbrido | O modelo de produção |

Resultado atual, NDCG@10 (veja o relatório completo):

- aleatório 0,127;
- popularidade 0,180;
- só conteúdo 0,364;
- só colaborativo 0,378;
- **híbrido 0,413**.

Os dois sinais se complementam. É o esperado pelo desenho do dataset: o conteúdo enxerga os
objetivos, e o colaborativo enxerga as tribos latentes (instrutor e período), que não estão no
texto.

**Cobertura** conta outra história: popularidade cobre 39% do catálogo no top-10, e o híbrido,
100%. Um modelo pode ter NDCG razoável e ainda concentrar a demanda nas mesmas aulas, lotando
turmas e esvaziando outras. Para um estúdio, isso é um problema operacional real.

## 5. A diferença é real? Bootstrap pareado

Médias de 201 alunos têm ruído. Para cada aluno calculamos `Δ = NDCG(híbrido) − NDCG(baseline)`
e reamostramos os alunos com reposição 1000 vezes. Os percentis 2,5 e 97,5 da média formam o
intervalo de 95%. No relatório atual, contra a popularidade em k = 10: Δ = +0,233, IC
[+0,186, +0,279]. O intervalo não cruza zero.

Por que **pareado**: o mesmo aluno é avaliado pelos dois modelos. Parear remove a variância
entre alunos ("alguns alunos são fáceis") e dá um intervalo mais estreito e honesto do que
comparar dois intervalos independentes.

## 6. Reprodutibilidade

- Dataset com seed fixa, embeddings por hashing determinístico (ADR 0002) e desempates
  explícitos por id em todos os ranqueamentos.
- O relatório não tem data de geração. O CI regenera e roda `git diff --exit-code`: se uma
  mudança de código altera os números, o PR precisa trazer o relatório novo, e o revisor vê o
  impacto no diff.
- Cada execução publicada (`--publish`) vai para o MinIO em `runs/AAAA-MM-DD/` (ADR 0008), o que
  forma o histórico de qualidade.

## 7. Trade-offs assumidos

- **Offline não é online.** O teste mede se o modelo prevê o que o aluno faria sem
  recomendação. Com recomendações em produção, o comportamento muda: há viés de exposição e um
  ciclo de retroalimentação. O passo seguinte é um teste A/B com métrica de negócio (reservas
  originadas da recomendação por aluno ativo).
- **Relevância binária.** Uma descoberta avaliada com nota 2 conta igual a uma com nota 5. Dá
  para usar ganho graduado no NDCG (nota como ganho), mas a maioria das descobertas não tem
  nota, e misturar escalas complicaria a leitura.
- **Popularidade é viés.** Aulas populares aparecem mais no teste porque são populares. O
  baseline de popularidade captura exatamente isso, e por isso precisa ser batido com folga.
- **Mundo sintético.** Os padrões foram plantados por nós (ADR 0006). Os números absolutos não
  valem para um estúdio real. O que transfere é o **protocolo**.
- **Pesos não ajustados.** Os pesos 0,5 / 0,4 / 0,1 foram escolhidos a priori. Ajustá-los olhando
  o teste seria vazamento de seleção. O correto é um terceiro recorte temporal de validação.

## 8. Perguntas de entrevista (e respostas)

**Por que não usar acurácia ou RMSE?**
O produto é uma lista ordenada curta, não a previsão de uma nota. RMSE premia acertar notas de
aulas que nunca apareceriam no topo; métricas top-k medem o que o aluno vê.

**Por que split temporal e não aleatório?**
O split aleatório coloca interações do futuro no treino. O colaborativo então "sabe" que o
vizinho fez a aula em agosto para prever a de julho, e as métricas sobem artificialmente. O
temporal reproduz a situação real: só conhecemos o passado.

**E o leave-one-out?**
Cada aluno teria seu próprio corte, e o vazamento entre alunos continuaria: a reserva de agosto
de um vizinho pode ajudar a prever a de março de outro. O corte global elimina isso.

**Por que excluir aulas já reservadas das candidatas?**
O objetivo é descoberta. Incluí-las tornaria o problema trivial (recomende o que ele já faz)
e as métricas sem significado.

**NDCG ou MAP?**
Os dois são sensíveis à posição. O NDCG desconta suavemente (log) e é o padrão de mercado para
listas. O MAP pune mais quando o primeiro acerto vem tarde. Uso NDCG como principal e MAP como
confirmação; quando discordam, olho a distribuição por aluno.

**Por que reportar cobertura se ela não mede relevância?**
Porque o estúdio tem capacidade física. Um recomendador que manda todo mundo para as mesmas
três aulas cria fila de espera e turmas vazias. A cobertura é uma métrica de saúde do
ecossistema; num próximo passo entraria a diversidade intra-lista.

**Como saber se a diferença é significativa?**
Bootstrap pareado por aluno, com IC de 95% da diferença. Se o intervalo não cruza zero, a
melhora é consistente nesta amostra. Prefiro o IC ao p-valor porque ele mostra o tamanho do
efeito.

**E se o modelo piorar em produção mesmo indo bem offline?**
É esperado em parte, pelo viés de exposição e pela mudança de comportamento. Por isso o
caminho é A/B com métrica de negócio e guardrails (cancelamentos, lotação). A avaliação
offline serve de filtro: só vai para o A/B o que bate os baselines offline.

**Como avaliar cold start?**
Com outro protocolo: alunos cujo primeiro histórico está no teste, recomendação só por
objetivos e popularidade, e as mesmas métricas. Está nos próximos passos. Misturar os dois
grupos esconderia o desempenho de cada um.

**Como o relatório evita que alguém "ajuste até ficar bonito"?**
Ele é determinístico e versionado. O CI quebra se o código mudar os números sem o relatório
novo no PR, então toda melhora alegada aparece no diff, com intervalo de confiança.

**Quanto custa rodar a avaliação?**
Menos de um segundo para 400 alunos e 80 aulas. O colaborativo em memória é O(alunos) por
consulta. Com 100 mil alunos, eu pré-computaria vizinhos em lote (GDS Node Similarity) e
avaliaria em paralelo por aluno.
