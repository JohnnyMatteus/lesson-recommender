# 0007. Combinação híbrida linear com normalização por requisição e pesos configuráveis

- Status: aceito
- Data: 2026-11-21

## Contexto

Os três sinais estão em escalas diferentes:

- cosseno de embeddings, em [-1, 1];
- soma de similaridades de vizinhos, sem teto;
- contagem de alunos (popularidade).

Somar os valores crus deixaria o sinal de maior escala dominar.

## Decisão

- Normalizar cada sinal entre as candidatas do próprio pedido:
  - **conteúdo:** min-max;
  - **colaborativo e popularidade:** divisão pelo máximo, para que zero continue significando
    "nenhuma evidência".
- Combinar linearmente: `score = w_c·conteúdo + w_col·colaborativo + w_pop·popularidade`.
- Pesos padrão: 0,3 / 0,6 / 0,1 (escolhidos no recorte de validação, ver `reports/avaliacao.md`), configuráveis por variável de ambiente (`LR_WEIGHT_*`).
  - Pesos negativos são rejeitados, assim como todos zerados.
  - A popularidade tem peso pequeno: serve de desempate e de rede de segurança no cold start.
- A resposta da API expõe a decomposição normalizada (`breakdown`) e frases de explicação
  derivadas dos mesmos sinais.

## Consequências

- A combinação é explicável: cada recomendação mostra quanto veio de cada sinal.
- As ablações do relatório (só conteúdo, só colaborativo) são o mesmo código com outros pesos.
- Min-max por pedido amplia diferenças pequenas quando todas as candidatas são parecidas. Um
  sinal constante vira zero, o que é intencional: ele não discrimina.
- Os pesos não foram ajustados no teste. O ajuste com validação temporal separada fica para
  depois (ADR 0004).

## Alternativas consideradas

- **Learning to rank (LightGBM LambdaMART):** melhor quando há muitas features e dados, mas
  aumenta a complexidade e reduz a explicabilidade. Fica para quando houver sinal online.
- **Cascata (colaborativo, com conteúdo só no cold start):** desperdiça o conteúdo para alunos
  com histórico, e a ablação mostra que os dois sinais se complementam.
- **Reciprocal rank fusion:** robusta a escalas, mas descarta a magnitude da evidência.
