"""Consultas Cypher do grafo de interações.

Modelo:
    (:Aluno)-[:RESERVOU {count, first_at, last_at}]->(:Aula)
    (:Aluno)-[:AVALIOU {score, at}]->(:Aula)
    (:Instrutor)-[:MINISTRA]->(:Aula)
    (:Aula)-[:É_DE]->(:Modalidade)

RESERVOU e AVALIOU são agregados: no máximo uma relação por par aluno-aula.
"""

CONSTRAINTS = (
    "CREATE CONSTRAINT aluno_id IF NOT EXISTS FOR (n:Aluno) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT aula_id IF NOT EXISTS FOR (n:Aula) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT instrutor_id IF NOT EXISTS FOR (n:Instrutor) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT modalidade_id IF NOT EXISTS FOR (n:Modalidade) REQUIRE n.id IS UNIQUE",
)

CLEAR_GRAPH = "MATCH (n) WHERE n:Aluno OR n:Aula OR n:Instrutor OR n:Modalidade DETACH DELETE n"

MERGE_MODALITIES = """
UNWIND $rows AS row
MERGE (m:Modalidade {id: row.id})
SET m.name = row.name, m.family = row.family
"""

MERGE_INSTRUCTORS = """
UNWIND $rows AS row
MERGE (i:Instrutor {id: row.id})
SET i.name = row.name
"""

MERGE_LESSONS = """
UNWIND $rows AS row
MERGE (a:Aula {id: row.id})
SET a.title = row.title, a.level = row.level, a.weekday = row.weekday,
    a.start_time = row.start_time, a.duration_minutes = row.duration_minutes,
    a.intensity = row.intensity, a.capacity = row.capacity, a.booked_seats = row.booked_seats,
    a.description = row.description, a.focus = row.focus,
    a.contraindications = row.contraindications
WITH a, row
MATCH (m:Modalidade {id: row.modality_id})
MATCH (i:Instrutor {id: row.instructor_id})
MERGE (a)-[:`É_DE`]->(m)
MERGE (i)-[:MINISTRA]->(a)
"""

MERGE_STUDENTS = """
UNWIND $rows AS row
MERGE (s:Aluno {id: row.id})
SET s.name = row.name, s.level = row.level, s.goals = row.goals,
    s.restrictions = row.restrictions
"""

MERGE_BOOKINGS = """
UNWIND $rows AS row
MATCH (s:Aluno {id: row.student_id})
MATCH (a:Aula {id: row.lesson_id})
MERGE (s)-[r:RESERVOU]->(a)
SET r.count = row.count, r.first_at = datetime(row.first_at), r.last_at = datetime(row.last_at)
"""

MERGE_RATINGS = """
UNWIND $rows AS row
MATCH (s:Aluno {id: row.student_id})
MATCH (a:Aula {id: row.lesson_id})
MERGE (s)-[r:AVALIOU]->(a)
SET r.score = row.score, r.at = datetime(row.at)
"""

GET_STUDENT = """
MATCH (s:Aluno {id: $student_id})
RETURN s.id AS id, s.name AS name, s.level AS level, s.goals AS goals,
       s.restrictions AS restrictions
"""

LIST_LESSONS = """
MATCH (i:Instrutor)-[:MINISTRA]->(a:Aula)-[:`É_DE`]->(m:Modalidade)
RETURN a {.*, modality_id: m.id, instructor_id: i.id} AS lesson
ORDER BY a.id
"""

LIST_MODALITIES = "MATCH (m:Modalidade) RETURN m.id AS id, m.name AS name, m.family AS family"

LIST_INSTRUCTORS = "MATCH (i:Instrutor) RETURN i.id AS id, i.name AS name"

STUDENT_HISTORY = """
MATCH (s:Aluno {id: $student_id})-[r:RESERVOU]->(a:Aula)
OPTIONAL MATCH (s)-[v:AVALIOU]->(a)
RETURN a.id AS lesson_id, r.count AS count, v.score AS score
"""

# O primeiro SET (no-op) pega o lock de escrita da aula; o WHERE seguinte lê a lotação já sob o
# lock, então duas reservas simultâneas não ocupam a mesma última vaga.
RECORD_BOOKING = """
MATCH (s:Aluno {id: $student_id})
MATCH (a:Aula {id: $lesson_id})
SET a.booked_seats = a.booked_seats
WITH s, a
WHERE a.booked_seats < a.capacity
SET a.booked_seats = a.booked_seats + 1
MERGE (s)-[r:RESERVOU]->(a)
ON CREATE SET r.count = 1, r.first_at = datetime($booked_at), r.last_at = datetime($booked_at)
ON MATCH SET r.count = r.count + 1, r.last_at = datetime($booked_at)
RETURN a.booked_seats AS booked_seats
"""

POPULARITY = """
MATCH (:Aluno)-[:RESERVOU]->(a:Aula)
RETURN a.id AS lesson_id, count(*) AS students
"""

# Colaborativo por vizinhança: mesma especificação de recommender/collaborative.py.
COLLABORATIVE_NEIGHBORHOOD = """
MATCH (u:Aluno {id: $student_id})-[:RESERVOU]->(:Aula)<-[:RESERVOU]-(v:Aluno)
WHERE v <> u
WITH u, v, count(*) AS shared
MATCH (u)-[:RESERVOU]->(ua:Aula)
WITH u, v, shared, count(ua) AS u_total
MATCH (v)-[:RESERVOU]->(va:Aula)
WITH u, v, shared, u_total, count(va) AS v_total
WITH u, v, toFloat(shared) / (u_total + v_total - shared) AS similarity
ORDER BY similarity DESC, v.id ASC
LIMIT $neighbors
MATCH (v)-[:RESERVOU]->(c:Aula)
WHERE NOT (u)-[:RESERVOU]->(c)
OPTIONAL MATCH (v)-[rating:AVALIOU]->(c)
WITH c, similarity * coalesce(toFloat(rating.score) / 5.0, $unrated_weight) AS contribution
RETURN c.id AS lesson_id, sum(contribution) AS score, count(*) AS support
ORDER BY score DESC, lesson_id ASC
"""
