# 0005. Regras de negócio como filtros duros antes do ranqueamento

- Status: aceito
- Data: 2026-11-21

## Contexto

Algumas recomendações são inaceitáveis, por melhor que seja a pontuação:

- aula lotada, porque o aluno clica e não consegue reservar;
- aula acima do nível do aluno, com risco de lesão e frustração;
- aula contraindicada para uma restrição declarada (ex.: Ashtanga para quem tem lesão lombar,
  aula intensa para gestante).

## Decisão

- `domain/rules.py` concentra as regras, que filtram as candidatas antes de qualquer pontuação.
- Nenhum peso compensa uma regra.
- **Nível:**
  - aula "livre" serve a todos;
  - fora isso, o nível da aula precisa ser o do aluno ou um abaixo. Duas faixas abaixo já é
    "fora do nível": o aluno avançado não recebe aula de iniciante.
- **Contraindicação:** qualquer interseção entre as restrições do aluno e as
  contraindicações da aula exclui a aula.
- **Lotação:** a aula é excluída quando `booked_seats >= capacity`.
- `EligibilityPolicy` liga e desliga cada regra. A API usa todas.
- A avaliação offline desliga a lotação. A ocupação é uma fotografia do presente e não existia
  quando as reservas históricas aconteceram. Aplicá-la no passado puniria os modelos por um
  estado que eles não poderiam conhecer.
- O gerador de dataset usa as mesmas funções de nível e contraindicação, então os alunos
  sintéticos nunca reservam aulas proibidas.

## Consequências

- As garantias de segurança são testáveis isoladamente, com casos de borda por regra.
- Baselines e modelo compartilham o filtro (`recommender/candidates.py`), o que mantém a
  comparação justa.
- A lotação é lida no momento do pedido. Se a fonte de ocupação atrasar, uma aula recém-lotada
  pode aparecer. O tratamento está no design doc.

## Alternativas consideradas

- **Penalidade na pontuação:** permitiria que uma aula contraindicada muito parecida
  aparecesse. Inaceitável para segurança.
- **Filtrar depois do top-k:** devolveria menos de k itens sem necessidade.
