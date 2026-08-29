# ---- Stage 1: builder ----
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-dev

COPY api/ ./api/
COPY workers/ ./workers/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY entrypoint.sh ./

RUN uv sync --frozen --no-dev


# ---- Stage 2: runtime ----
FROM python:3.13-slim AS runtime

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY --from=builder /app/pyproject.toml ./
COPY --from=builder /app/uv.lock ./

COPY --from=builder /app/api ./api
COPY --from=builder /app/workers ./workers
COPY --from=builder /app/alembic ./alembic
COPY --from=builder /app/alembic.ini ./
COPY --from=builder /app/entrypoint.sh ./entrypoint.sh

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    C_FORCE_ROOT=1


RUN uv sync --frozen --no-dev && chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]