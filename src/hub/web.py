"""Owner dashboard — plain HTTP served from the same app as the MCP server.

These are the *human* routes: the self-contained page at `/`, its embedded demo
clip, and the live JSON at `/api/*`. They are NOT MCP tools — Agora's cloud agent
never sees them; it only calls the `@mcp.tool()`s over `/mcp`. Co-hosting them on
the MCP server's Starlette app (via `custom_route`) is what gives one clean Cloud
Run URL: `/` for the judge, `/mcp` for the bot, both reading the same baked DB.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from hub.core import service

# web/ sits at the repo root (src/hub/web.py -> parents[2]); the Dockerfile copies
# it to /app/web. Same resolution works locally and on Cloud Run.
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
DEFAULT_PERIOD = "2026-07"


def register_web_routes(mcp: FastMCP) -> None:
    """Attach the dashboard's HTTP routes to `mcp`'s app. `custom_route` only adds
    routes — the `/mcp` streamable-http endpoint Agora depends on is untouched."""

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard(_: Request) -> Response:
        """The judge-clickable Demo URL — the owner dashboard (self-contained HTML)."""
        return FileResponse(WEB_DIR / "index.html", media_type="text/html")

    @mcp.custom_route("/demoVideo.mp4", methods=["GET"])
    async def demo_video(_: Request) -> Response:
        """The embedded end-to-end demo clip (784 KB), served from the image."""
        return FileResponse(WEB_DIR / "demoVideo.mp4", media_type="video/mp4")

    @mcp.custom_route("/api/overview", methods=["GET"])
    async def api_overview(request: Request) -> Response:
        """Live dashboard payload — the same Core the voice bot reads, one fetch."""
        period = request.query_params.get("period", DEFAULT_PERIOD)
        return JSONResponse(service.dashboard_overview(period).model_dump())

    @mcp.custom_route("/api/devices/{device_id}/recapture", methods=["POST"])
    async def api_recapture(request: Request) -> Response:
        """The 'act' — queue a re-read for a device (beat #5)."""
        device_id = request.path_params["device_id"]
        return JSONResponse(service.request_recapture(device_id).model_dump())
