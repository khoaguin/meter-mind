"""REST adapter — every route returns 200 + the frozen numbers; unknown ids -> 404.

The adapter is thin, so these tests mostly guard wiring: routes bound to the
right service fn, path/query params threaded, NotFoundError mapped to 404.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from hub.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed(seeded_session: Session) -> None:
    """Routes read the DB at request time — bind + seed a tmp DB for every API test."""


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_devices_lists_all_three() -> None:
    resp = client.get("/devices")
    assert resp.status_code == 200
    assert {d["device_id"] for d in resp.json()} == {
        "kiosk1-water",
        "kiosk2-water",
        "kiosk3-elec",
    }


def test_readings_route_returns_usage() -> None:
    # WHY: beat #1 over HTTP — the dashboard reads usage 620 from this route.
    resp = client.get("/devices/kiosk3-elec/readings")
    assert resp.status_code == 200
    assert resp.json()["usage"] == pytest.approx(620, abs=1e-6)


def test_anomaly_route_returns_factor() -> None:
    # WHY: beat #2 over HTTP.
    resp = client.get("/devices/kiosk3-elec/anomaly")
    assert resp.status_code == 200
    assert resp.json()["factor"] == 4.0


def test_unpaid_route_counts_two() -> None:
    resp = client.get("/unpaid")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_invoice_route_amount() -> None:
    resp = client.get("/tenants/room2/invoice")
    assert resp.status_code == 200
    assert resp.json()["amount"] == pytest.approx(270_000, abs=1e-3)


def test_recapture_route_queued() -> None:
    resp = client.post("/devices/kiosk3-elec/recapture")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


@pytest.mark.parametrize(
    "path",
    ["/devices/ghost/readings", "/devices/ghost/anomaly", "/tenants/ghost/invoice"],
)
def test_unknown_id_returns_404(path: str) -> None:
    # WHY: unknown device/tenant is a 404, never a 500 or a silent empty body.
    assert client.get(path).status_code == 404
