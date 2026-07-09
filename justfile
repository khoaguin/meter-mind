_cyan := '\033[0;36m'
_red := '\033[0;31m'
_green := '\033[0;32m'
_nc := '\033[0m'

set shell := ["bash", "-cu"]

# meter-mind — task runner. `just` to list.
default:
    @just --list

# Install deps + pre-commit hooks
init:
    uv sync
    uv run pre-commit install --install-hooks
    uv run pre-commit install --hook-type pre-push

# Download jomjol model + digit crops into data/
fetch-assets:
    uv run python scripts/fetch_assets.py

# Run tests (serial). Use for the integration suite: `just test -m integration`.
test *args:
    uv run pytest {{args}}

# Default suite in parallel (pytest-xdist) — faster on CI. Integration stays
# excluded by addopts; run it serially via `just test -m integration`.
test-fast *args:
    uv run pytest -n auto {{args}}

# Lint (ruff) — `just lint --fix` to auto-fix
lint *args:
    uv run ruff check {{args}} .

# Format
fmt:
    uv run ruff format .

# Type check whole project
types:
    uv run pyrefly check

# Everything CI runs
check: lint types test-fast

# Seed the hub SQLite DB from core/seed.yaml (init_db + load_seed)
hub-seed:
    PYTHONPATH=src uv run python -m hub.db.seed_loader

# Teardown + re-seed the hub DB
hub-db-reset:
    rm -f data/hub.db && just hub-seed

# Serve the hub REST API (spine dashboard)
hub-api:
    PYTHONPATH=src uv run uvicorn hub.api:app --reload --port 8000

# Serve the hub MCP endpoint (voice track / Agora) over streamable-http on /mcp
hub-mcp:
    PYTHONPATH=src uv run python -m hub.mcp_server

# Start local MQTT broker (mosquitto)
broker-up:
    docker compose up -d mosquitto

# Stop broker
broker-down:
    docker compose down

# Remove caches
clean:
    @echo -e "{{_red}}Cleaning caches…{{_nc}}"
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    @echo -e "{{_green}}Done.{{_nc}}"