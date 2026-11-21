"""Colaborativo por vizinhança de alunos (user-based kNN com Jaccard).

Esta é a especificação de referência do algoritmo. A consulta Cypher em
`graph/cypher.py::COLLABORATIVE_NEIGHBORHOOD` implementa exatamente a mesma conta no grafo, e
o teste de integração compara as duas saídas.

1. Vizinhos de u: alunos v != u que reservaram ao menos uma aula em comum.
2. Similaridade: Jaccard entre os conjuntos de aulas reservadas, |Iu inter Iv| / |Iu uniao Iv|.
3. Mantém os N vizinhos mais similares (empate: id do aluno, crescente).
4. Para cada aula c que v reservou e u não: score(c) += sim(u, v) * peso(v, c), onde
   peso = nota/5 quando v avaliou c, ou UNRATED_WEIGHT quando só reservou.
"""

from __future__ import annotations

from collections.abc import Mapping, Set

from lesson_recommender.domain.models import CollaborativeSignal

UNRATED_WEIGHT = 0.6


def jaccard(a: Set[str], b: Set[str]) -> float:
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def neighborhood_scores(
    student_id: str,
    booked_by_student: Mapping[str, Set[str]],
    ratings: Mapping[tuple[str, str], int],
    *,
    neighbors: int,
) -> dict[str, CollaborativeSignal]:
    """Calcula o sinal colaborativo para `student_id`.

    `booked_by_student` mapeia aluno -> aulas reservadas; `ratings` mapeia (aluno, aula) -> nota.
    """
    if neighbors <= 0:
        raise ValueError(f"neighbors deve ser positivo: {neighbors}")
    target = booked_by_student.get(student_id, frozenset())
    if not target:
        return {}

    similarities = [
        (jaccard(target, lessons), other)
        for other, lessons in booked_by_student.items()
        if other != student_id and target & lessons
    ]
    similarities.sort(key=lambda pair: (-pair[0], pair[1]))

    scores: dict[str, float] = {}
    support: dict[str, int] = {}
    for similarity, neighbor in similarities[:neighbors]:
        for lesson_id in booked_by_student[neighbor] - target:
            rating = ratings.get((neighbor, lesson_id))
            weight = rating / 5.0 if rating is not None else UNRATED_WEIGHT
            scores[lesson_id] = scores.get(lesson_id, 0.0) + similarity * weight
            support[lesson_id] = support.get(lesson_id, 0) + 1

    return {
        lesson_id: CollaborativeSignal(score=score, support=support[lesson_id])
        for lesson_id, score in scores.items()
    }
