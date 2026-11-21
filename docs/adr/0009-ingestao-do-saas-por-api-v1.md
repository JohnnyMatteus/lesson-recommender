# 0009. Ingestão do SaaS por API v1 com credencial de serviço, com ACL e um recomendador por tenant

- Status: aceito
- Data: 2026-11-21

## Contexto

O recomendador precisa de aulas, alunos e reservas reais do SaaS de estúdios (monolito Laravel
multitenant). O SaaS expõe uma API REST v1 autenticada por JWT do Keycloak (claim `tenant`).
Hoje ele publica um único evento de domínio (`WaitlistPromoted`, interno ao Laravel, sem
broker): não existe barramento, outbox nem stream de eventos de reserva.

Os modelos também diferem. O SaaS tem sessões datadas, alunos sem nível/objetivos/restrições e
nenhum conceito de modalidade, intensidade ou contraindicação. O recomendador trabalha com
aulas recorrentes e esses atributos.

## Decisão

1. **Ingestão por pull na API v1** (`GET /v1/sessions` e `GET /v1/sessions/{id}/bookings`),
   com **credencial de serviço** (client credentials do Keycloak, uma por estúdio, token com a
   claim `tenant` e papel de equipe). Janela de 90 dias para trás e 14 para a frente, em
   janelas de 31 dias (limite da API), sincronizada a cada 5 minutos. O snapshot de um estúdio
   é trocado de forma atômica; se a sincronização falha, o anterior continua valendo.
2. **ACL** (`saas/`): `payloads.py` descreve o contrato do SaaS, `acl.py` o traduz.
   - série de sessões vira uma aula recorrente (`series_id`); ocupação vem da próxima turma;
   - só reserva `confirmed` é sinal; lista de espera e cancelamento ficam de fora;
   - nível e objetivos do aluno são **inferidos** do histórico; restrições de saúde **nunca**
     são inferidas (ficam vazias);
   - modalidade, intensidade, foco e contraindicações vêm de uma tabela por palavra-chave do
     título (`catalog.py`); título desconhecido vira aula "livre" sem foco, que não é bloqueada
     nem favorecida por suposição.
3. **Isolamento por tenant**: um `HybridRecommender` (repositório, conteúdo e vizinhança
   próprios) por estúdio. Não há índice compartilhado nem consulta que cruze estúdios.
4. **Identidade**: o `sub` do Keycloak não é o id do aluno nas reservas (o SaaS usa um id
   próprio). O serviço resolve o id chamando `GET /v1/me` com o token do próprio aluno e guarda
   o resultado por (tenant, sub) por 15 minutos.

## Consequências

- Nenhuma mudança no SaaS: o recomendador só consome a API pública versionada.
- Dados com até 5 minutos de atraso, suficiente para recomendar; a lotação exibida pode
  envelhecer nesse intervalo.
- O custo é uma chamada por sessão da janela por ciclo (N+1 nas reservas). Aceitável para
  estúdios (dezenas de turmas por semana); não escala para redes grandes.
- A credencial de serviço exige que o realm tenha um client com service account por estúdio,
  com a claim `tenant` e papel `studio_admin`. O realm de exemplo do SaaS ainda não tem; ver
  `docs/integracao-saas.md`.
- Aluno novo, sem reserva confirmada, não existe no snapshot: a rota responde 404 até a
  primeira reserva (cold start fica como evolução).
- Neo4j fica de fora do caminho do SaaS: cada snapshot é pequeno e roda em memória.

## Alternativas consideradas

- **Eventos (broker + outbox no SaaS):** dados quase em tempo real e sem N+1, mas exige que o
  SaaS publique eventos de reserva e cancelamento, o que ele não faz, e um broker novo no
  ecossistema. Fica como evolução: a ACL já recebe payloads normalizados, então trocar pull
  por eventos só muda a origem.
- **Leitura direta do banco do SaaS:** acopla o recomendador ao esquema interno e fura o
  isolamento por tenant que o SaaS garante na aplicação.
- **Um índice único com `tenant_id` em cada nó:** menos objetos, porém um erro de filtro vaza
  vizinhos entre estúdios. Preferimos isolamento estrutural.
- **Token do usuário para ingerir:** aluno não pode listar reservas de outros; só a equipe.
