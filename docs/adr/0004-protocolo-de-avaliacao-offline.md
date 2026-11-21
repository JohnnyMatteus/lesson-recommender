# 0004. Protocolo de avaliação offline: split temporal global e relevância por descoberta

- Status: aceito
- Data: 2026-11-21

## Contexto

Sem um protocolo claro, qualquer número de precisão é enganoso. Os riscos principais são:

- **vazamento temporal:** treinar com reservas posteriores às que se tenta prever;
- **alvo errado:** contar como acerto uma aula que o aluno já frequenta toda semana;
- **comparação injusta:** baselines competindo num conjunto de candidatas diferente do modelo.

## Decisão

1. **Split temporal global.** O corte é o quantil 80% das datas de reserva. Tudo antes vai
   para o treino (reservas e avaliações); tudo depois, para o teste. O corte é um instante
   único para todos os alunos: nenhum dado do futuro de ninguém entra no treino.
2. **Relevante = descoberta.** São as aulas que o aluno reservou pela primeira vez depois do
   corte. Repetições não contam, porque o produto existe para ajudar a descobrir aulas.
3. **População avaliada.** Alunos com histórico de treino e ao menos uma descoberta no teste.
   Cold start fica de fora desta métrica e é registrado como próximo passo.
4. **Candidatas.** Todos os modelos, inclusive os baselines, ranqueiam o mesmo conjunto: aulas
   não reservadas no treino que passam nas regras de negócio.
5. **Métricas em k = 5 e 10:**
   - precision@k, recall@k, NDCG@k (relevância binária) e MAP@k (AP normalizado por
     min(|rel|, k));
   - cobertura do catálogo.
6. **Comparação:**
   - baselines: aleatório (seed fixa por aluno) e popularidade (alunos distintos no treino);
   - ablações: só conteúdo e só colaborativo;
   - bootstrap pareado (1000 reamostragens de alunos) para o IC de 95% da diferença de NDCG
     entre o híbrido e cada baseline.
7. **Relatório Markdown determinístico** em `reports/avaliacao.md`. O CI regenera o relatório
   e falha se ele mudar sem commit.

## Consequências

- Os números são comparáveis entre versões. Toda mudança no recomendador aparece como diff no
  relatório, revisável no PR.
- O protocolo mede descoberta, não retenção nem satisfação. Métricas online (CTR, reservas
  originadas da recomendação) ficam para quando houver tráfego real.
- Os pesos padrão foram escolhidos a priori, não ajustados no teste. Ajustar pesos exige um
  recorte de validação separado (próximos passos), senão o teste deixa de ser teste.

## Alternativas consideradas

- **Split aleatório de interações:** vaza o futuro e infla as métricas.
- **Leave-one-out por aluno (última interação):** útil, mas cada aluno tem seu próprio corte.
  Uma reserva de março de um aluno pode estar no teste enquanto a de agosto de outro está no
  treino, e o vazamento entre alunos continua.
- **Amostrar 100 negativas por aluno:** comum na literatura e conhecido por distorcer o
  ranking entre modelos. Com dezenas de candidatas, ranqueamos todas.
