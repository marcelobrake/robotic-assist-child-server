# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source.
COPY src ./src
COPY pyproject.toml ./

ENV PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8000 \
    PROMPTS_REPOSITORY_PATH=/app/prompts

# Non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/prompts \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/v1/health/live').status==200 else sys.exit(1)" \
    || exit 1

CMD ["uvicorn", "robotic_assist_child_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
