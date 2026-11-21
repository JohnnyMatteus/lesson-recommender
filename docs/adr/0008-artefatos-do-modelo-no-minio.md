# 0008. Artefatos do modelo em object storage S3 (MinIO localmente) atrás de uma porta

- Status: aceito
- Data: 2026-11-21

## Contexto

Cada execução da avaliação produz dois artefatos que vale guardar:

- o **relatório de avaliação**, que mostra a qualidade do modelo naquele dia;
- o **índice de embeddings** das aulas: a matriz de vetores e um manifesto com a ordem dos ids
  e o embedder usado.

O relatório versionado no Git (`reports/avaliacao.md`) mostra só a versão atual do código.
Já o histórico por execução, que permite comparar a qualidade de ontem com a de hoje e
reaproveitar um índice sem recalcular, precisa de um lugar próprio. Em produção esse lugar
seria o S3. Para o ambiente local, o caminho natural é um emulador compatível.

## Decisão

- Criar uma porta `ArtifactStore` (`artifacts/store.py`) com `put` e `get`, e dois adaptadores:
  - `LocalArtifactStore`: diretório local. É o padrão, usado em testes e sem infraestrutura.
  - `S3ArtifactStore`: recebe um cliente boto3 injetado. O endpoint é configurável
    (`LR_S3_ENDPOINT_URL`).
- Localmente, o adaptador S3 aponta para o **MinIO** do docker-compose. Na AWS, basta deixar o
  endpoint vazio e trocar as credenciais: o código é o mesmo.
- Organizar as chaves por data: `runs/AAAA-MM-DD/avaliacao.md`,
  `runs/AAAA-MM-DD/embeddings/lessons.npy` e `runs/AAAA-MM-DD/embeddings/manifest.json`.
  O bucket tem versionamento ligado (`deploy/minio/create-bucket.sh`). Assim, duas execuções no
  mesmo dia não perdem a anterior.
- Publicar por `lesson-recommender evaluate --publish`. O serviço `seed` do compose faz isso a
  cada carga.
- Validar as chaves: chave vazia, caminho absoluto ou `..` são rejeitados, para que nada escape
  do diretório ou do prefixo.
- `boto3` fica no extra `[s3]`. A imagem Docker instala o extra; o núcleo não depende dele.

## Consequências

- O histórico de qualidade fica consultável por data, sem poluir o Git.
- Os testes do adaptador S3 usam um cliente falso com a mesma interface (`put_object` e
  `get_object`). Não há rede nem container. A integração real com o MinIO é exercitada no
  compose (`make up`).
- Mais um serviço no ambiente local, mas só no perfil `core` e leve.
- A API ainda não lê o índice publicado: recalcula os embeddings na subida, o que é barato com
  hashing. Carregar o índice do storage passa a valer com sentence-transformers (próximos
  passos).

## Alternativas consideradas

- **LocalStack:** emula muitos serviços AWS. O projeto só precisa de object storage, e o MinIO
  é mais leve e mais simples de operar.
- **Só o sistema de arquivos:** funciona localmente, mas não exercita o caminho de produção, e
  o índice não fica compartilhável entre réplicas da API.
- **MLflow para tracking de experimentos:** mais completo (métricas, parâmetros, UI), mas pesado
  para a fundação. Pode usar o mesmo MinIO como backend de artefatos no futuro.
