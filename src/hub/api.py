"""FastAPI REST adapter — thin translation of HTTP routes to `core.service` calls.

Holds no logic of its own: each route calls one service fn and returns the same
Pydantic model. Unknown ids surface as HTTP 404. Serves the spine dashboard.
Run: `just hub-api`.
"""

from fastapi import FastAPI, HTTPException

from hub.core import service
from hub.core.contract import (
    AnomalyExplanation,
    Invoice,
    ReadingsSummary,
    RecaptureAck,
    UnpaidList,
)

app = FastAPI(title="Meter-Mind Hub API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/devices")
def devices() -> list[dict[str, str]]:
    return service.list_devices()


@app.get("/devices/{device_id}/readings")
def readings(device_id: str, period: str = "2026-07") -> ReadingsSummary:
    try:
        return service.query_readings(device_id, period)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/devices/{device_id}/anomaly")
def anomaly(device_id: str) -> AnomalyExplanation:
    try:
        return service.explain_anomaly(device_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/unpaid")
def unpaid(period: str = "2026-07") -> UnpaidList:
    return service.list_unpaid(period)


@app.get("/tenants/{tenant_id}/invoice")
def invoice(tenant_id: str, period: str = "2026-07") -> Invoice:
    try:
        return service.compute_invoice(tenant_id, period)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/devices/{device_id}/recapture")
def recapture(device_id: str) -> RecaptureAck:
    return service.request_recapture(device_id)
