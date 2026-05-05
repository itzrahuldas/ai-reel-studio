FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/api_src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl build-essential \
    && apt-get clean

COPY apps/api/pyproject.toml apps/api/README.md /api_src/
COPY apps/api/app /api_src/app
COPY apps/api/alembic /api_src/alembic
COPY apps/api/alembic.ini /api_src/alembic.ini

RUN python -m pip install --upgrade pip \
    && pip install -e /api_src

COPY apps/worker /app

CMD ["celery", "-A", "app.main:celery_app", "worker", "--loglevel=info", "--queues=default,generation,rendering,publishing"]
