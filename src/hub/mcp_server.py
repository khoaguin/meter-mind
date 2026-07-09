"""FastMCP adapter — the same `core.service` fns exposed as MCP tools.

Agora's cloud agent function-calls against these tool docstrings, so each is a
one-line description mirroring its demo beat. Served over streamable-HTTP on
`/mcp` (public tunnel required — Agora can't reach localhost). Run: `just hub-mcp`.
"""

from mcp.server.fastmcp import FastMCP

from hub.core import service

mcp = FastMCP("meter-mind-hub", host="0.0.0.0", port=8000)


@mcp.tool()
def query_readings(device_id: str, period: str = "2026-07") -> dict:
    """Get a meter's usage total and per-day series for a billing period."""
    return service.query_readings(device_id, period).model_dump()


@mcp.tool()
def explain_anomaly(device_id: str) -> dict:
    """Explain why a meter's consumption spiked, in plain Vietnamese."""
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
