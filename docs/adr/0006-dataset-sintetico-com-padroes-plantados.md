# 0006. Dataset sintético reprodutível com padrões plantados

- Status: aceito
- Data: 2026-11-21

## Contexto

O projeto é de portfólio, e o domínio é fictício: não há dados reais de estúdio. Um dataset
puramente aleatório não tem sinal nenhum, e qualquer modelo empataria com o aleatório. O
contrário também é ruim: um dataset gerado com a mesma fórmula do modelo faria o modelo
parecer perfeito.

## Decisão

- `dataset/generator.py` gera, com `random.Random(seed)`:
  - aulas: modalidade, nível, instrutor, horário, intensidade, descrição, foco e
    contraindicações;
  - alunos: objetivos e restrições;
  - reservas e avaliações ao longo de 26 semanas.
- Padrões plantados:
  - **Objetivos × foco da aula:** sinal que o conteúdo enxerga.
  - **Tribos latentes:** grupos com instrutores, modalidades e período favoritos. Só parte
    disso aparece no texto; o resto só o colaborativo enxerga.
  - **Período do dia preferido.**
  - **Descoberta gradual:** o aluno começa com duas aulas e descobre novas por afinidade, em
    ritmo de curiosidade individual.
  - **Notas correlacionadas com a afinidade,** mais ruído gaussiano.
- A afinidade usada pelo gerador **não** é a função do recomendador:
  - o gerador usa variáveis latentes (tribo, período) que o modelo não vê;
  - o modelo vê só texto, histórico e grafo.

## Consequências

- O relatório mostra uma hierarquia plausível e explicável: aleatório < popularidade <
  conteúdo ≈ colaborativo < híbrido.
- A mesma seed gera exatamente o mesmo dataset, o que os testes verificam.
- Os números absolutos valem para este mundo sintético, não para estúdios reais. O roteiro de
  avaliação deixa isso explícito.

## Alternativas consideradas

- **Dataset público de filmes (MovieLens):** fora do domínio, e não exercita regras de nível e
  contraindicação.
- **Fixtures escritas à mão:** boas para testes de unidade (usadas em `tests/factories.py`),
  pequenas demais para avaliação.
