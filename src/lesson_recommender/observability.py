"""Logs estruturados (JSON), métricas Prometheus e traces OpenTelemetry."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram

_STANDARD_ATTRIBUTES = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys() | {"message", "asctime"}
)

REQUESTS = Counter(
    "lr_http_requests_total", "Requisições HTTP atendidas", ["route", "method", "status"]
)
REQUEST_LATENCY = Histogram(
    "lr_http_request_duration_seconds", "Latência das requisições HTTP", ["route", "method"]
)
RECOMMENDATIONS = Counter(
    "lr_recommendations_total", "Aulas recomendadas, por sinal dominante", ["dominant_signal"]
)
EMPTY_RECOMMENDATIONS = Counter(
    "lr_empty_recommendations_total", "Pedidos sem nenhuma aula elegível"
)


class JsonFormatter(logging.Formatter):
    """Uma linha JSON por evento, com trace_id quando há span ativo e campos de `extra`."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            payload["trace_id"] = format(span.trace_id, "032x")
            payload["span_id"] = format(span.span_id, "016x")
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


def configure_tracing(service_name: str, otlp_endpoint: str | None) -> None:
    """Sem endpoint, os spans existem (e dão trace_id aos logs), mas não são exportados."""
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces"))
        )
    trace.set_tracer_provider(provider)
