"""Vocabulário controlado do estúdio: como cada objetivo do aluno é descrito em texto.

O modelo de conteúdo transforma os objetivos do aluno nestas frases e as compara, via
embeddings, com o texto das aulas.
"""

from lesson_recommender.domain.models import Goal

GOAL_QUERIES: dict[Goal, str] = {
    Goal.FLEXIBILITY: "flexibilidade alongamento mobilidade articular",
    Goal.STRENGTH: "fortalecimento força core resistência muscular",
    Goal.STRESS_RELIEF: "relaxamento respiração redução do estresse calma",
    Goal.POSTURE: "postura alinhamento postural coluna consciência corporal",
    Goal.CONDITIONING: "condicionamento ritmo dinâmico cardiorrespiratório",
    Goal.REHABILITATION: "reabilitação baixo impacto progressão segura",
}
