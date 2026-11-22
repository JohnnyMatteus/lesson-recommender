# Padrões e SOLID no código

Só entra aqui o que o código realmente tem. Caminhos relativos a este arquivo; links apontam
para a linha.

## Padrões

| Padrão | Onde | Problema que resolve | Trade-off |
|---|---|---|---|
| Portas e adaptadores | [`domain/ports.py`](../../src/lesson_recommender/domain/ports.py#L34), [`recommender/ports.py`](../../src/lesson_recommender/recommender/ports.py#L10) | O núcleo (ranqueamento, regras, avaliação) roda sem Neo4j, Redis ou S3, inclusive na avaliação offline em memória ([ADR 0001](../adr/0001-arquitetura-hexagonal-com-portas.md)). | `Protocol` estrutural: um adaptador que esquece um método só falha no mypy, não em tempo de import. |
| Repository | [`CatalogRepository`](../../src/lesson_recommender/domain/ports.py#L34) e [`BookingRepository`](../../src/lesson_recommender/domain/ports.py#L60), com [`Neo4jRepository`](../../src/lesson_recommender/graph/repository.py#L45) e [`InMemoryRepository`](../../src/lesson_recommender/adapters/memory_repository.py#L25) | Recomendador e caso de uso de reserva leem e gravam entidades de domínio sem conhecer Cypher. | O colaborativo existe duas vezes (Python e Cypher) e precisa concordar; o teste de integração garante isso. |
| Adapter | [`S3ArtifactStore`](../../src/lesson_recommender/artifacts/store.py#L49), [`SentenceTransformerEmbedder`](../../src/lesson_recommender/embeddings/sentence.py#L18), [`RedisRecommendationCache`](../../src/lesson_recommender/adapters/redis_cache.py#L93) | Traduz boto3, sentence-transformers e redis-py para as portas do projeto (LocalStack local e S3 na AWS com o mesmo código). | Uma camada a mais para manter quando a biblioteca muda. |
| Strategy | [`EmbeddingProvider`](../../src/lesson_recommender/domain/ports.py#L25) (hashing ou sentence-transformers) e [`RankingModel`](../../src/lesson_recommender/evaluation/baselines.py#L14) (híbrido, popularidade, aleatório) | Troca o algoritmo de embedding sem tocar no modelo de conteúdo; a avaliação compara modelos pela mesma interface `rank`. | O hashing é determinístico e sem rede, mas semanticamente mais pobre ([ADR 0002](../adr/0002-porta-de-embeddings.md)). |
| Factory | [`build_embedder`](../../src/lesson_recommender/embeddings/factory.py#L17), [`build_cache`](../../src/lesson_recommender/bootstrap.py#L77) | Escolhe a implementação pela configuração e importa a dependência opcional só quando usada. | Validação da configuração acontece no start, não no import. |
| Decorator | [`CachedRecommender`](../../src/lesson_recommender/recommender/cached.py#L9) | Cache sem alterar o `HybridRecommender`: mesma interface `Recommender`, ligado só quando `LR_REDIS_URL` existe ([`bootstrap.py`](../../src/lesson_recommender/bootstrap.py#L87)). | Recomendações de outros alunos podem mostrar `seats_left` defasado até o TTL (120 s por padrão); só o aluno que reservou é invalidado. Uma recomendação calculada antes da reserva e gravada depois do DEL sobrevive até o TTL. |
| Caso de uso (application service) | [`BookLesson.execute`](../../src/lesson_recommender/application/booking.py#L41) | Orquestra regra dura, gravação e invalidação do cache num lugar só, testável com repositório em memória. | A invalidação é chamada direta, não evento; com mais consumidores da reserva valeria um outbox. |
| Composition root | [`create_production_app`](../../src/lesson_recommender/bootstrap.py#L87) | Único lugar que conhece todas as implementações concretas. | Mudou a montagem, muda só ali. |

Não usamos Specification nem Chain of Responsibility: as três regras duras são um
[`rejection_reason`](../../src/lesson_recommender/domain/rules.py#L40) de poucas linhas,
configurável por [`EligibilityPolicy`](../../src/lesson_recommender/domain/rules.py#L21). Forçar
uma cadeia de objetos não pagaria a complexidade.

## SOLID

| Princípio | Onde | Como aparece | Trade-off |
|---|---|---|---|
| S (responsabilidade única) | [`redis_cache.py`](../../src/lesson_recommender/adapters/redis_cache.py#L93) x [`cached.py`](../../src/lesson_recommender/recommender/cached.py#L9) | O decorator decide *quando* usar o cache; o adaptador decide *como* serializar e onde guardar. | Dois arquivos para uma funcionalidade. |
| O (aberto/fechado) | [`CachedRecommender`](../../src/lesson_recommender/recommender/cached.py#L9) | Cache entrou sem editar `HybridRecommender` nem a API. | — |
| L (substituição de Liskov) | [`InMemoryRepository`](../../src/lesson_recommender/adapters/memory_repository.py#L25) e [`Neo4jRepository`](../../src/lesson_recommender/graph/repository.py#L45) | Ambos cumprem o mesmo contrato, inclusive `record_booking` devolvendo `False` quando lotou; `CachedRecommender` substitui o híbrido na API. | Exige testes de contrato (integração com Neo4j). |
| I (segregação de interfaces) | [`CatalogRepository`](../../src/lesson_recommender/domain/ports.py#L34), [`CollaborativeSource`](../../src/lesson_recommender/domain/ports.py#L52), [`BookingRepository`](../../src/lesson_recommender/domain/ports.py#L60) | A avaliação depende só de leitura; só a reserva conhece a escrita. | Os adaptadores concretos implementam as três. |
| D (inversão de dependência) | [`create_app`](../../src/lesson_recommender/api/app.py#L54), [`BookLesson`](../../src/lesson_recommender/application/booking.py#L23) | API e caso de uso recebem abstrações (`Recommender`, `RecommendationCache`); quem cria é o bootstrap. | Leitura mais indireta para quem chega ao código. |
