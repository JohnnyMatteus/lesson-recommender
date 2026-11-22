# 0010. LocalStack no S3 local

- Status: aceito. Substitui a parte do ADR 0008 que escolhia o servidor S3 do ambiente local e rejeitava o LocalStack. O resto do ADR 0008 (porta `ArtifactStore`, chaves por data, versionamento) continua valendo.
- Data: 2026-11-22

## Contexto

As imagens do servidor S3 e do cliente de linha de comando usados no ambiente local saíram dos registros públicos (conferido por manifesto em 22/11/2026). O `make up` deixou de subir em máquina limpa. O ADR 0008 tinha rejeitado o LocalStack por ser mais pesado do que o necessário; esse argumento perde peso diante de um ambiente que não sobe.

## Decisão

- O S3 local passa a ser o `localstack/localstack:4.4.0` com `SERVICES=s3`, porta publicada só em `127.0.0.1`.
- `deploy/localstack/init-s3.sh` (bit executável no Git, montado em `/etc/localstack/init/ready.d`) cria o bucket de artefatos e liga o versionamento, e confere o resultado. O healthcheck consulta `/_localstack/init/ready` e só passa com o script `SUCCESSFUL` e nenhum `ERROR`; o `seed` espera por ele (`service_healthy`).
- O cliente boto3 usa endereçamento path-style quando há endpoint configurado.
- As credenciais de desenvolvimento passam a `dev-only-localstack`; `LR_MINIO_API_PORT` vira `LR_S3_PORT` e a porta do console some (o LocalStack community não tem console).
- O CI ganha o job `s3-localstack`: sobe o LocalStack pelo compose real com `--wait`, roda o `seed` (publicação real dos artefatos) e um teste de integração de put, get e versionamento.

## Consequências

- O LocalStack community não persiste entre recriações: os artefatos locais são descartáveis. `make seed` os republica.
- Não é prova de conformidade com a AWS; só o comportamento exercitado pelo job está verificado.
- A imagem é maior do que a do servidor anterior.

## Alternativas consideradas

- **Outra imagem de servidor S3:** não avaliada com manifesto conferido; mantém o risco de nova retirada.
- **Só o sistema de arquivos (`LR_ARTIFACTS_BACKEND=local`):** continua disponível, mas não exercita o caminho S3.
