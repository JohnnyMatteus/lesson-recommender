#!/bin/sh
# Cria o bucket de artefatos do modelo no MinIO local (idempotente).
set -eu
mc alias set local http://minio:9000 "$LR_S3_ACCESS_KEY" "$LR_S3_SECRET_KEY"
mc mb --ignore-existing "local/$LR_S3_BUCKET"
mc version enable "local/$LR_S3_BUCKET"
echo "bucket pronto: $LR_S3_BUCKET"
