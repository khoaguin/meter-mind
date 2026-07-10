# MeterMind hub MCP server — served over streamable-HTTP on /mcp for Agora's
# cloud agent. Cloud Run sets PORT (default 8080); hub.mcp_server reads it.
FROM python:3.12-slim-bookworm

# uv from the official image (matches the repo's uv-based toolchain).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

# Project metadata first so the dependency layer caches across code-only changes.
COPY pyproject.toml uv.lock README.md ./
COPY src src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
# `hub` is not an installed package — it's imported via PYTHONPATH=src (as in the justfile).
ENV PYTHONPATH="/app/src"

# Bake the demo SQLite DB (seeded from src/hub/core/seed.yaml) into the image.
# The 5 hub tools are read-only, so a build-time seed is all Cloud Run needs and
# the container starts with zero external dependencies.
ENV HUB_DB_PATH="/app/data/hub.db"
RUN python -m hub.db.seed_loader

# Documentation only — Cloud Run routes to whatever PORT it injects.
EXPOSE 8080
CMD ["python", "-m", "hub.mcp_server"]
