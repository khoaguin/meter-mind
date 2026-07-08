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

# Run tests
test *args:
    uv run pytest {{args}}

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
check: lint types test

# Start local MQTT broker (mosquitto)
broker-up:
    docker compose up -d mosquitto

# Stop broker
broker-down:
    docker compose down
