"""Core stub contract — each test names the demo beat it defends.

These are the frozen demo numbers Track B's voice loop and Track A's dashboard
both bind to; a change here is a change to the demo script.
"""

import pytest

from hub.core import service


def test_query_readings_usage_is_620() -> None:
    # WHY: beat #1 — "kiosk3 used 620 kWh"; the headline number the chart totals to.
    assert service.query_readings("kiosk3-elec").usage == 620


def test_query_readings_series_reconciles_to_usage() -> None:
    # WHY: the per-day series must sum to the stated usage or the chart total lies.
    summary = service.query_readings("kiosk3-elec")
    assert sum(point.value for point in summary.series) == pytest.approx(620, abs=1e-6)


def test_explain_anomaly_factor_is_4x() -> None:
    # WHY: beat #2 (money shot) — 4× spike on 2026-07-14.
    anomaly = service.explain_anomaly("kiosk3-elec")
    assert anomaly.has_anomaly is True
    assert anomaly.factor == 4.0
    assert anomaly.detected_at == "2026-07-14"


def test_explain_anomaly_clean_device_has_no_anomaly() -> None:
    # WHY: only kiosk3 spiked — water meters must report clean, not a false positive.
    assert service.explain_anomaly("kiosk1-water").has_anomaly is False


def test_list_unpaid_counts_two() -> None:
    # WHY: beat #3 — "a couple unpaid" is exactly room2 + room3.
    unpaid = service.list_unpaid()
    assert unpaid.count == 2
    assert {tenant.tenant_id for tenant in unpaid.tenants} == {"room2", "room3"}


def test_compute_invoice_amount_is_derived() -> None:
    # WHY: beat #4 — 18 m³ × 15000 = 270,000; amount is derived, never a stale literal.
    invoice = service.compute_invoice("room2")
    assert invoice.amount == 270_000
    assert invoice.amount == invoice.usage * invoice.tariff_rate


def test_request_recapture_known_device_is_queued() -> None:
    # WHY: beat #5 — a known device queues; the voice agent confirms the recapture.
    assert service.request_recapture("kiosk3-elec").status == "queued"


def test_request_recapture_unknown_device_is_soft_ack() -> None:
    # WHY: recapture on an unknown device is a soft ack, not a hard 404.
    assert service.request_recapture("ghost-meter").status == "unknown_device"


def test_unknown_device_raises_not_found() -> None:
    # WHY: reads on an unknown id fail loudly so the adapter can map to 404.
    with pytest.raises(service.NotFoundError):
        service.query_readings("ghost-meter")


def test_unknown_tenant_raises_not_found() -> None:
    with pytest.raises(service.NotFoundError):
        service.compute_invoice("room99")
