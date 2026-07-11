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

# Open the owner dashboard — the same server as hub-mcp hosts it at / (seeds first if needed)
dashboard:
    @test -f data/hub.db || just hub-seed
    @echo "Dashboard → http://localhost:8000/   (MCP for Agora → /mcp)"
    PYTHONPATH=src uv run python -m hub.mcp_server

# --- VN utility agent (Vertex AI Agent Engine) --------------------------------

_gcp_project := 'ai-playground-458112'
_agent_region := 'asia-southeast1'
# Deployed engine backing the ask_utility_info MCP tool (see README).
_agent_resource := env_var_or_default('UTILITY_AGENT_RESOURCE_NAME', 'projects/161661253262/locations/asia-southeast1/reasoningEngines/507930391567400960')

# Chat with the VN utility agent locally (Vertex backend, ADC auth)
agent-run:
    GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT={{_gcp_project}} GOOGLE_CLOUD_LOCATION=global \
        uv run --group agent adk run vn_utility_agent

# Update the deployed VN utility agent in place (create a new engine: `just agent-deploy-new`)
agent-deploy:
    uv run --group agent adk deploy agent_engine \
        --project {{_gcp_project}} --region {{_agent_region}} \
        --display_name vn-utility-info \
        --description "General VN electricity/water utility info, grounded via Google Search" \
        --agent_engine_id "$(basename {{_agent_resource}})" vn_utility_agent

# First-time deploy — creates a NEW engine and prints its resource name
agent-deploy-new:
    uv run --group agent adk deploy agent_engine \
        --project {{_gcp_project}} --region {{_agent_region}} \
        --display_name vn-utility-info \
        --description "General VN electricity/water utility info, grounded via Google Search" \
        vn_utility_agent

# Live golden-question suite against the deployed agent (network + ADC)
agent-test:
    UTILITY_AGENT_RESOURCE_NAME={{_agent_resource}} uv run pytest -m manual tests/test_utility_agent_golden.py -v

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