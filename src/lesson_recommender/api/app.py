"""API HTTP. Recebe o recomendador pronto (injeção de dependência), sem saber de Neo4j."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import FastAPI, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from lesson_recommender.api.schemas import (
    BookingIn,
    BookingOut,
    ErrorResponse,
    RecommendationOut,
    RecommendationsResponse,
    RejectionResponse,
)
from lesson_recommender.application.booking import BookLesson
from lesson_recommender.domain.errors import (
    BookingRejectedError,
    InvalidRequestError,
    LessonNotFoundError,
    StudentNotFoundError,
)
from lesson_recommender.observability import (
    BOOKINGS,
    EMPTY_RECOMMENDATIONS,
    RECOMMENDATIONS,
    REQUEST_LATENCY,
    REQUESTS,
)
from lesson_recommender.recommender.hybrid import MAX_K, Recommendation
from lesson_recommender.recommender.ports import Recommender

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def _dominant_signal(item: Recommendation, recommender: Recommender) -> str:
    w = recommender.weights
    contributions = {
        "content": w.content * item.breakdown.content,
        "collaborative": w.collaborative * item.breakdown.collaborative,
        "popularity": w.popularity * item.breakdown.popularity,
    }
    return max(contributions, key=lambda key: contributions[key])


def create_app(recommender: Recommender, book_lesson: BookLesson | None = None) -> FastAPI:
    app = FastAPI(
        title="lesson-recommender",
        version="0.1.0",
        description="Recomendações de aulas de yoga e pilates com explicação.",
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

    @app.get("/health", tags=["operação"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", tags=["operação"], include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

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
        with tracer.start_as_current_span("recommend") as span:
            span.set_attribute("student.id", student_id)
            span.set_attribute("recommendation.k", k)
            items = recommender.recommend(student_id, k)
            span.set_attribute("recommendation.count", len(items))
        if not items:
            EMPTY_RECOMMENDATIONS.inc()
        for item in items:
            RECOMMENDATIONS.labels(_dominant_signal(item, recommender)).inc()
        logger.info(
            "recomendações geradas",
            extra={"student_id": student_id, "k": k, "returned": len(items)},
        )
        w = recommender.weights
        return RecommendationsResponse(
            student_id=student_id,
            k=k,
            weights={
                "content": w.content,
                "collaborative": w.collaborative,
                "popularity": w.popularity,
            },
            items=[RecommendationOut.from_domain(item) for item in items],
        )

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

    return app
