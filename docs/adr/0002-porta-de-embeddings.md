# 0002. Porta de embeddings: hashing determinístico por padrão, sentence-transformers opcional

- Status: aceito
- Data: 2026-11-21

## Contexto

A similaridade de conteúdo compara o texto das aulas (modalidade, nível, intensidade,
instrutor, descrição) com o perfil do aluno. Modelos de sentence embeddings dão vetores
semânticos melhores, mas:

- `sentence-transformers` puxa PyTorch (centenas de MB) e baixa o modelo na primeira execução;
- o CI ficaria lento e dependente da internet, e o brief proíbe testes que acessam serviços
  externos;
- os vetores podem variar entre versões de biblioteca e hardware, e o relatório de avaliação
  deixaria de ser reprodutível bit a bit.

## Decisão

Uma porta `EmbeddingProvider` com duas implementações:

1. **`HashingEmbedder` (padrão):**
   - unigramas e bigramas, normalizados (minúsculas, sem acento, sem stopwords);
   - frequência sublinear (1 + log tf);
   - feature hashing com sinal, usando `blake2b`, que é estável entre processos (o `hash()`
     do Python não é);
   - 1024 dimensões e norma L2.

   Não precisa de treino nem de rede, e é determinístico.
2. **`SentenceTransformerEmbedder` (opcional):**
   - ativado por `LR_EMBEDDINGS_BACKEND=sentence-transformers`;
   - modelo em `LR_EMBEDDINGS_MODEL`;
   - instalado pelo extra `pip install '.[sentence-transformers]'`;
   - importado de forma preguiçosa: sem o extra, falha com `ConfigurationError` explicando
     como instalar.

## Consequências

- CI e testes rodam em segundos, sem baixar nada.
- O relatório em `reports/avaliacao.md` é idêntico em qualquer máquina, e o CI verifica isso.
- O hashing não entende sinônimos: "relaxamento" e "descanso" não se aproximam. No dataset
  sintético isso é pouco relevante, porque o vocabulário é controlado. Com descrições reais
  escritas por instrutores, a troca para sentence-transformers deve ser medida com o mesmo
  relatório (próximos passos).
- Colisões de hash existem, mas com 1024 dimensões e um vocabulário de centenas de termos o
  efeito é desprezível.

## Alternativas consideradas

- **TF-IDF ajustado ao catálogo:** exige `fit` e estado. O vetor de uma aula muda quando outra
  é adicionada, e isso complica cache e reprodutibilidade.
- **sentence-transformers como único backend:** CI pesado e não determinístico.
- **API de embeddings hospedada:** custo, latência, dependência de rede e envio de dados do
  estúdio a terceiros.
