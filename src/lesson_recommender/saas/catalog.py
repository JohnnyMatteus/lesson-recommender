"""Enriquecimento do catálogo: o SaaS só conhece título, horário, instrutor e vagas.

Nível, intensidade, foco e contraindicações são conceitos do recomendador. Esta tabela os
deriva do título da aula (palavras-chave sem acento). Aula que não casa com nenhuma regra
entra como "livre", intensidade moderada e sem foco: nunca é bloqueada nem favorecida por
suposição.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from lesson_recommender.domain.models import Goal, Level, Modality, Restriction


@dataclass(frozen=True, slots=True)
class CatalogRule:
    keywords: tuple[str, ...]
    modality: Modality
    intensity: int
    focus: frozenset[Goal]
    contraindications: frozenset[Restriction]
    description: str


FALLBACK_MODALITY = Modality("outras", "Outras aulas", "outras")

# Ordem importa: a primeira regra que casa vence (mais específicas antes).
RULES: tuple[CatalogRule, ...] = (
    CatalogRule(
        ("restaurativ",),
        Modality("restaurativa", "Yoga Restaurativa", "yoga"),
        1,
        frozenset({Goal.STRESS_RELIEF, Goal.REHABILITATION}),
        frozenset(),
        "Uso de apoios e almofadas para descanso ativo.",
    ),
    CatalogRule(
        ("yin",),
        Modality("yin", "Yin Yoga", "yoga"),
        1,
        frozenset({Goal.FLEXIBILITY, Goal.STRESS_RELIEF}),
        frozenset(),
        "Posturas passivas longas no solo, trabalhando tecidos profundos.",
    ),
    CatalogRule(
        ("vinyasa", "flow"),
        Modality("vinyasa", "Vinyasa Flow", "yoga"),
        4,
        frozenset({Goal.CONDITIONING, Goal.STRENGTH, Goal.FLEXIBILITY}),
        frozenset({Restriction.PREGNANCY, Restriction.HYPERTENSION}),
        "Transições contínuas sincronizadas com a respiração.",
    ),
    CatalogRule(
        ("ashtanga", "power"),
        Modality("ashtanga", "Ashtanga", "yoga"),
        5,
        frozenset({Goal.STRENGTH, Goal.CONDITIONING}),
        frozenset({Restriction.PREGNANCY, Restriction.HYPERTENSION}),
        "Série fixa e vigorosa, com contagem de respirações.",
    ),
    CatalogRule(
        ("hatha", "yoga"),
        Modality("hatha", "Hatha Yoga", "yoga"),
        2,
        frozenset({Goal.FLEXIBILITY, Goal.POSTURE, Goal.STRESS_RELIEF}),
        frozenset(),
        "Posturas clássicas sustentadas com atenção ao alinhamento.",
    ),
    CatalogRule(
        ("aparelho", "reformer"),
        Modality("pilates-aparelhos", "Pilates de Aparelhos", "pilates"),
        3,
        frozenset({Goal.STRENGTH, Goal.POSTURE, Goal.REHABILITATION}),
        frozenset(),
        "Trabalho guiado por molas e roldanas, com apoio do instrutor.",
    ),
    CatalogRule(
        ("pilates",),
        Modality("pilates-solo", "Pilates Solo", "pilates"),
        3,
        frozenset({Goal.STRENGTH, Goal.POSTURE}),
        frozenset(),
        "Exercícios no tapete com bola, faixa elástica e anel.",
    ),
)

_LEVEL_WORDS: tuple[tuple[str, Level], ...] = (
    ("avancad", Level.ADVANCED),
    ("intermediari", Level.INTERMEDIATE),
    ("iniciante", Level.BEGINNER),
    ("basico", Level.BEGINNER),
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def match_rule(title: str) -> CatalogRule | None:
    folded = _fold(title)
    return next((r for r in RULES if any(k in folded for k in r.keywords)), None)


def level_from_title(title: str) -> Level:
    folded = _fold(title)
    return next((level for word, level in _LEVEL_WORDS if word in folded), Level.ALL)
