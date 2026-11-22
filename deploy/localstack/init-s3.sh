#!/bin/sh
# Cria o bucket de artefatos do modelo com versionamento ligado (ADR 0008 e ADR 0010). O LocalStack executa os
# scripts de /etc/localstack/init/ready.d quando está pronto; o healthcheck do compose só fica saudável depois
# deste script. Idempotente. Variável de ambiente: LR_S3_BUCKET.
set -eu

: "${LR_S3_BUCKET:?defina LR_S3_BUCKET}"

if ! awslocal s3api head-bucket --bucket "$LR_S3_BUCKET" 2>/dev/null; then
  awslocal s3api create-bucket --bucket "$LR_S3_BUCKET"
fi
awslocal s3api put-bucket-versioning --bucket "$LR_S3_BUCKET" --versioning-configuration Status=Enabled
# Confere o que foi aplicado: se o versionamento não ficar ligado, o init falha em vez de fingir.
awslocal s3api get-bucket-versioning --bucket "$LR_S3_BUCKET" | grep -q '"Enabled"'
echo "bucket pronto: $LR_S3_BUCKET (versionado)"
