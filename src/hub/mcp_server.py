"""FastMCP adapter — the same `core.service` fns exposed as MCP tools.

Agora's cloud agent function-calls against these tool docstrings, so each is a
one-line description mirroring its demo beat. Served over streamable-HTTP on
`/mcp` (public tunnel required — Agora can't reach localhost). Run: `just hub-mcp`.
"""

import os

from mcp.server.fastmcp import FastMCP

from hub.core import service
from hub.core.contract import (
    AnomalyExplanation,
    Invoice,
    ReadingsSummary,
    RecaptureAck,
    UnpaidList,
)

MCP_PORT: int = int(os.environ.get("HUB_MCP_PORT", "8100"))  # distinct from REST's 8000
mcp = FastMCP("meter-mind", host="0.0.0.0", port=MCP_PORT)


@mcp.tool()
def query_readings(device_id: str, period: str = "2026-07") -> ReadingsSummary:
    """Get a meter's usage total and reading history for a month.
    Use for 'how much did kiosk 3 use this month'.
    device_id like 'kiosk3-elec' or 'kiosk1-water'; period is 'YYYY-MM'."""
    return service.query_readings(device_id, period)


@mcp.tool()
def explain_anomaly(device_id: str) -> AnomalyExplanation:
    """Explain WHY a meter is unusually high/low, in plain English.
    Use for 'why is kiosk 3 so high this month'.
    Returns a spike factor, the day it happened, and an English explanation."""
    return service.explain_anomaly(device_id)


@mcp.tool()
def list_unpaid(period: str = "2026-07") -> UnpaidList:
    """List tenants who have NOT paid this month, with amount due.
    Use for 'who hasn't paid'. period is 'YYYY-MM'."""
    return service.list_unpaid(period)


@mcp.tool()
def compute_invoice(tenant_id: str, period: str = "2026-07") -> Invoice:
    """Compute a tenant's bill for the month (usage × tariff, in VND).
    Use for 'what's room 2's bill'. tenant_id like 'room2'."""
    return service.compute_invoice(tenant_id, period)


@mcp.tool()
def request_recapture(device_id: str) -> RecaptureAck:
    """Ask a meter to take a fresh reading now (queues a re-read).
    Use for 'ask kiosk 3 to re-read'. Returns a queued acknowledgement — no bill changes."""
    return service.request_recapture(device_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
