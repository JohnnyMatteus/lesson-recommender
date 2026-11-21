"""Sincronização periódica: cada estúdio é lido com a sua credencial e vira um recomendador."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from lesson_recommender.domain.errors import RecommenderError
from lesson_recommender.saas.client import SaasApiClient
from lesson_recommender.saas.ingest import ingest_tenant
from lesson_recommender.saas.tenants import TenantRecommenders

logger = logging.getLogger(__name__)


class TenantSyncer:
    def __init__(
        self,
        clients: Mapping[str, SaasApiClient],
        tenants: TenantRecommenders,
        *,
        lookback_days: int,
        lookahead_days: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._clients = clients
        self._tenants = tenants
        self._lookback = lookback_days
        self._lookahead = lookahead_days
        self._clock = clock

    def sync_all(self) -> dict[str, bool]:
        """Falha de um estúdio não derruba os outros; o snapshot anterior continua valendo."""
        outcome: dict[str, bool] = {}
        for tenant, client in self._clients.items():
            try:
                dataset = ingest_tenant(
                    client,
                    now=self._clock(),
                    lookback_days=self._lookback,
                    lookahead_days=self._lookahead,
                )
                self._tenants.replace(tenant, dataset)
            except (RecommenderError, ValueError) as error:
                logger.error("sincronização falhou", extra={"tenant": tenant, "error": str(error)})
                outcome[tenant] = False
                continue
            logger.info(
                "estúdio sincronizado",
                extra={
                    "tenant": tenant,
                    "lessons": len(dataset.lessons),
                    "students": len(dataset.students),
                    "bookings": len(dataset.bookings),
                },
            )
            outcome[tenant] = True
        return outcome
