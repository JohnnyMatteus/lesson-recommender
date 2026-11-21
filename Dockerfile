FROM python:3.12-slim-bookworm AS build
WORKDIR /src
RUN pip install --no-cache-dir build==1.2.2
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /dist/*.whl /tmp/
RUN for wheel in /tmp/*.whl; do pip install --no-cache-dir "${wheel}[s3]"; done && rm /tmp/*.whl
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
CMD ["uvicorn", "--factory", "lesson_recommender.bootstrap:create_production_app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
