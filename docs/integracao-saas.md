# Integração com o SaaS de estúdios

Decisão e motivos: [ADR 0009](adr/0009-ingestao-do-saas-por-api-v1.md).

## Fluxo

```
front do SaaS --JWT do aluno--> lesson-recommender --(credencial de serviço)--> API v1 do SaaS
                                     |   GET /v1/sessions, /v1/sessions/{id}/bookings
                                     +--(token do aluno)--> GET /v1/me   (id do aluno)
```

## Endpoint

`GET /tenants/{tenant}/students/{id}/recommendations?k=`

| Parte | Descrição |
|---|---|
| `tenant` | slug do estúdio, igual à claim `tenant` do token (ex.: `estudio-lotus`) |
| `id` | id do aluno no SaaS (o `id` de `GET /v1/me`), não o `sub` do Keycloak |
| `k` | quantas aulas, de 1 a 50 (padrão 10) |
| `Authorization` | `Bearer <access token do Keycloak do SaaS>` |

### Autenticação e autorização

O token é validado localmente, como na API do SaaS: assinatura RS256 (só RS256), `exp`, `iss`
(`LR_SAAS_ISSUER`), `aud` (`studio-api`) e `sub`, com chaves do JWKS do Keycloak em cache. A
claim `tenant` é obrigatória. Depois, nesta ordem:

1. o `tenant` do caminho precisa ser igual ao do token (senão 403);
2. o estúdio precisa estar configurado neste serviço (senão 404);
3. o `id` do caminho precisa ser o aluno dono do token (senão 403). Isso vale para qualquer
   papel: nem a equipe lê recomendação de aluno por este endpoint.

### Resposta 200

```json
{
  "student_id": "01JD0EXEMPLO0ALUNA000000A",
  "k": 3,
  "weights": {"content": 0.3, "collaborative": 0.6, "popularity": 0.1},
  "items": [
    {
      "lesson": {
        "id": "01JD0EXEMPLO0SERIE0000001",
        "title": "Yin Yoga",
        "modality_id": "yin",
        "instructor_id": "01JD0EXEMPLO0INSTR000001",
        "level": "livre",
        "schedule": "terça 07:00",
        "intensity": 1,
        "seats_left": 6
      },
      "score": 0.81,
      "breakdown": {"content": 0.7, "collaborative": 0.9, "popularity": 0.4},
      "reasons": ["Trabalha seus objetivos: flexibilidade"]
    }
  ]
}
```

`lesson.id` é o `series_id` do SaaS: o front liga a aula às sessões da série em
`GET /v1/sessions` e reserva por `POST /v1/sessions/{session}/bookings`. `schedule` está no
fuso do estúdio.

### Erros

| Status | Quando | Corpo |
|---|---|---|
| 401 | token ausente, malformado, expirado, assinatura/emissor/audiência inválidos, sem `tenant` | `{"detail": "não autenticado"}` + `WWW-Authenticate: Bearer` |
| 403 | tenant do caminho diferente do token; aluno diferente do dono do token | `{"detail": "..."}` |
| 404 | estúdio não atendido, ou aluno sem reserva confirmada ainda (cold start) | `{"detail": "..."}` |
| 422 | `k` fora de 1..50 | detalhe do FastAPI |
| 502 | o SaaS não respondeu ao resolver o aluno (`/v1/me`) | `{"detail": "SaaS indisponível"}` |

O motivo exato do 401 vai só para o log do serviço.

### CORS

Só as origens de `LR_CORS_ORIGINS` (padrão `http://localhost:5173`, o front do SaaS em
desenvolvimento), método `GET`, cabeçalhos `Authorization` e `Content-Type`, sem cookies.
O preflight `OPTIONS` é respondido pelo próprio serviço.

### Exemplo

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/tenants/estudio-lotus/students/$MEMBER_ID/recommendations?k=5"
```

## Configuração

| Variável | Descrição |
|---|---|
| `LR_SAAS_API_URL` | base da API do SaaS (ex.: `http://localhost:8081/api`); liga o modo SaaS |
| `LR_SAAS_TOKEN_URL` | endpoint de token do realm (client credentials) |
| `LR_SAAS_ISSUER` / `LR_SAAS_AUDIENCE` | `iss` e `aud` esperados (`studio-api`) |
| `LR_SAAS_JWKS_URL` | JWKS do realm; alternativa: `LR_SAAS_JWT_PUBLIC_KEY_FILE` (PEM) |
| `LR_SAAS_TENANTS` | JSON `{"<slug>": {"client_id": "...", "client_secret": "..."}}` |
| `LR_SAAS_REFRESH_SECONDS` | intervalo da sincronização (padrão 300) |
| `LR_SAAS_LOOKBACK_DAYS` / `LR_SAAS_LOOKAHEAD_DAYS` | janela de histórico e de turmas futuras |
| `LR_CORS_ORIGINS` | JSON com as origens do front, ex.: `["http://localhost:5173"]` |

Em modo SaaS a rota de demonstração `/students/{id}/recommendations` (dataset sintético,
sem autenticação) não é publicada.

## O que o SaaS precisa fornecer

- Um client por estúdio no Keycloak com **service account**, a claim `tenant` do estúdio e o
  papel `studio_admin` (a lista de reservas de uma sessão exige papel de equipe), com
  audiência `studio-api`. O realm de exemplo do SaaS (`realm-estudios.json`) ainda não define
  esse client: precisa ser acrescentado lá.
- Os tokens de aluno do front (`studio-web`) já levam `aud=studio-api` e a claim `tenant`.

## Limites conhecidos

- Nível e objetivos do aluno são inferidos do histórico; restrições de saúde ficam vazias,
  porque o SaaS não as guarda. Uma contraindicação real depende de o SaaS passar a expô-las.
- Modalidade, intensidade e contraindicações da aula vêm de palavras-chave do título
  (`saas/catalog.py`).
- Sem avaliações (notas): o SaaS não tem esse conceito; o colaborativo usa só reservas.
