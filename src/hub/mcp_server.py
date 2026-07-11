"""FastMCP adapter — the same `core.service` fns exposed as MCP tools.

Agora's cloud agent function-calls against these tool docstrings, so each is a
one-line description mirroring its demo beat. Served over streamable-HTTP on
`/mcp` (public tunnel required — Agora can't reach localhost). Run: `just hub-mcp`.

This file is ONLY the AI's tools. The human owner-dashboard (served at `/` on the
same Cloud Run service) lives in `hub.web` and is attached at the bottom via
`register_web_routes(mcp)` — those are plain HTTP routes the browser hits, never
MCP tools, so Agora neither sees nor needs them.
"""

import os

from mcp.server.fastmcp import FastMCP

from hub import utility_info
from hub.core import service
from hub.web import register_web_routes

# Cloud Run injects PORT (default 8080); locally we fall back to 8000.
mcp = FastMCP(
    "meter-mind-hub", host="0.0.0.0", port=int(os.environ.get("PORT", "8000"))
)


@mcp.tool()
def query_readings(device_id: str, period: str = "2026-07") -> dict:
    """Get a meter's usage total and per-day series for a billing period."""
    return service.query_readings(device_id, period).model_dump()


@mcp.tool()
def explain_anomaly(device_id: str) -> dict:
    """Explain why a meter's consumption spiked, in plain English."""
    return service.explain_anomaly(device_id).model_dump()


@mcp.tool()
def list_unpaid(period: str = "2026-07") -> dict:
    """List tenants with an outstanding bill for the period."""
    return service.list_unpaid(period).model_dump()


@mcp.tool()
def compute_invoice(tenant_id: str, period: str = "2026-07") -> dict:
    """Compute one tenant's invoice (usage × tariff) for the period."""
    return service.compute_invoice(tenant_id, period).model_dump()


@mcp.tool()
def request_recapture(device_id: str) -> dict:
    """Queue a fresh image capture for a meter device."""
    return service.request_recapture(device_id).model_dump()


@mcp.tool()
def ask_utility_info(question: str) -> dict:
    """General utility information for Vietnam: current electricity/water
    tariffs, planned outage schedules (e.g. Ho Chi Minh City), how pricing
    tiers work, regulations. Use for general knowledge questions only — NOT
    for this landlord's tenants, invoices, meter readings, or payments (use
    the other tools for those)."""
    return utility_info.ask_utility_info(question)


# Attach the human owner-dashboard (page + /api/*) to this server's HTTP app.
# Plain HTTP routes, not MCP tools — /mcp (streamable-http) is untouched.
register_web_routes(mcp)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
