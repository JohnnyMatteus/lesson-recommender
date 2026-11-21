"""Um recomendador por estúdio: os dados de tenants diferentes nunca se misturam.

Cada tenant tem repositório, modelo de conteúdo e vizinhança próprios. O colaborativo de um
estúdio não enxerga alunos de outro, e a troca do snapshot é atômica (substitui o objeto).
"""

from __future__ import annotations

from collections.abc import Callable

from lesson_recommender.domain.models import Dataset
from lesson_recommender.recommender.hybrid import HybridRecommender

RecommenderFactory = Callable[[Dataset], HybridRecommender]


class TenantRecommenders:
    def __init__(self, factory: RecommenderFactory) -> None:
        self._factory = factory
        self._by_tenant: dict[str, HybridRecommender] = {}

    def replace(self, tenant: str, dataset: Dataset) -> None:
        self._by_tenant[tenant] = self._factory(dataset)

    def get(self, tenant: str) -> HybridRecommender | None:
        return self._by_tenant.get(tenant)

    def tenants(self) -> list[str]:
        return sorted(self._by_tenant)
