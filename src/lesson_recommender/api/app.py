"""API HTTP. Recebe o recomendador pronto (injeção de dependência), sem saber de Neo4j."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated

from fastapi import APIRouter, FastAPI, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from lesson_recommender.api.render import build_response
from lesson_recommender.api.schemas import (
    BookingIn,
    BookingOut,
    ErrorResponse,
    RecommendationsResponse,
    RejectionResponse,
)
from lesson_recommender.application.booking import BookLesson
from lesson_recommender.domain.errors import (
    AuthenticationError,
    BookingRejectedError,
    ForbiddenError,
    IntegrationError,
    InvalidRequestError,
    LessonNotFoundError,
    StudentNotFoundError,
)
from lesson_recommender.observability import BOOKINGS, REQUEST_LATENCY, REQUESTS
from lesson_recommender.recommender.hybrid import MAX_K
from lesson_recommender.recommender.ports import Recommender

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def create_app(
    recommender: Recommender | None = None,
    book_lesson: BookLesson | None = None,
    *,
    tenant_router: APIRouter | None = None,
    cors_origins: Sequence[str] = (),
) -> FastAPI:
    """`recommender` serve a rota de demonstração (sintético); `tenant_router`, a do SaaS."""
    app = FastAPI(
        title="lesson-recommender",
        version="0.1.0",
        description="Recomendações de aulas de yoga e pilates com explicação.",
    )

    if cors_origins:
        # Só o front do SaaS, só leitura, sem cookies: a autenticação é o Bearer.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )

    @app.middleware("http")
    async def metrics_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")
        elapsed = time.perf_counter() - started
        REQUEST_LATENCY.labels(template, request.method).observe(elapsed)
        REQUESTS.labels(template, request.method, str(response.status_code)).inc()
        logger.info(
            "requisição atendida",
            extra={
                "route": template,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 2),
            },
        )
        return response

    @app.exception_handler(StudentNotFoundError)
    async def student_not_found(_: Request, error: StudentNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(LessonNotFoundError)
    async def lesson_not_found(_: Request, error: LessonNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(BookingRejectedError)
    async def booking_rejected(_: Request, error: BookingRejectedError) -> JSONResponse:
        BOOKINGS.labels("rejected").inc()
        return JSONResponse(status_code=409, content={"detail": str(error), "reason": error.reason})

    @app.exception_handler(InvalidRequestError)
    async def invalid_request(_: Request, error: InvalidRequestError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(AuthenticationError)
    async def unauthenticated(_: Request, error: AuthenticationError) -> JSONResponse:
        logger.warning("autenticação recusada", extra={"reason": str(error)})
        return JSONResponse(
            status_code=401,
            content={"detail": "não autenticado"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden(_: Request, error: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(IntegrationError)
    async def upstream_failure(_: Request, error: IntegrationError) -> JSONResponse:
        logger.error("falha no SaaS", extra={"error": str(error)})
        return JSONResponse(status_code=502, content={"detail": "SaaS indisponível"})

    @app.get("/health", tags=["operação"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", tags=["operação"], include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if recommender is not None:

        @app.get(
            "/students/{student_id}/recommendations",
            response_model=RecommendationsResponse,
            responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
            tags=["recomendações"],
        )
        def recommendations(
            student_id: Annotated[str, Path(min_length=1, max_length=64)],
            k: Annotated[int, Query(ge=1, le=MAX_K, description="Quantidade de aulas")] = 10,
        ) -> RecommendationsResponse:
            return build_response(recommender, student_id, k)

        if book_lesson is not None:

            @app.post(
                "/students/{student_id}/bookings",
                status_code=201,
                response_model=BookingOut,
                responses={404: {"model": ErrorResponse}, 409: {"model": RejectionResponse}},
                tags=["reservas"],
            )
            def book(
                student_id: Annotated[str, Path(min_length=1, max_length=64)], body: BookingIn
            ) -> BookingOut:
                with tracer.start_as_current_span("book_lesson") as span:
                    span.set_attribute("student.id", student_id)
                    span.set_attribute("lesson.id", body.lesson_id)
                    booking = book_lesson.execute(student_id, body.lesson_id)
                BOOKINGS.labels("created").inc()
                logger.info(
                    "reserva registrada",
                    extra={"student_id": student_id, "lesson_id": body.lesson_id},
                )
                return BookingOut(
                    student_id=booking.student_id,
                    lesson_id=booking.lesson_id,
                    booked_at=booking.booked_at,
                )

    if tenant_router is not None:
        app.include_router(tenant_router)

    return app
