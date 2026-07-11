"""Real Core (DB-backed) — each test names the demo beat / invariant it defends.

Uses the seeded tmp-DB fixture (bound to the module engine in conftest), so these
call the exact production `service` fns the REST/MCP adapters call. Everything is
deterministic code — no model runs, so nothing is mocked.
"""

import inspect
from collections.abc import Callable

import pytest
from sqlmodel import Session

from hub.core import contract, service


def test_query_readings_usage(seeded_session: Session) -> None:
    # WHY: beat #1 — usage 620; and the series must reconcile to it (Σ deltas == usage).
    summary = service.query_readings("kiosk3-elec")
    assert summary.usage == pytest.approx(620, abs=1e-6)
    assert summary.series
    assert sum(point.value for point in summary.series) == pytest.approx(
        summary.usage, abs=1e-9
    )


def test_anomaly_factor_and_date(seeded_session: Session) -> None:
    # WHY: beat #2 (money shot) — re-derived from the stored series, not a seed field.
    anomaly = service.explain_anomaly("kiosk3-elec")
    assert anomaly.has_anomaly is True
    assert anomaly.factor == 4.0
    assert anomaly.detected_at == "2026-07-14"
    assert anomaly.explanation  # non-empty English


def test_clean_device_has_no_anomaly(seeded_session: Session) -> None:
    # WHY: a flat water meter must report clean, not a false positive (no Claude call either).
    anomaly = service.explain_anomaly("kiosk1-water")
    assert anomaly.has_anomaly is False
    assert anomaly.factor is None


def test_unpaid_count_and_members(seeded_session: Session) -> None:
    # WHY: beat #3 — "a couple unpaid" is exactly room2 + room3.
    unpaid = service.list_unpaid()
    assert unpaid.count == 2
    assert {tenant.tenant_id for tenant in unpaid.tenants} == {"room2", "room3"}


def test_invoice_room2_is_270k(seeded_session: Session) -> None:
    # WHY: beat #4 — 18 m³ × 15000 = 270,000; amount is DERIVED, never a stored literal.
    invoice = service.compute_invoice("room2")
    assert invoice.amount == pytest.approx(270_000, abs=1e-3)
    assert invoice.paid is False
    assert invoice.amount == pytest.approx(invoice.usage * invoice.tariff_rate)


def test_recapture_queued_and_unknown(seeded_session: Session) -> None:
    # WHY: beat #5 — known device queues; unknown is a soft ack, not a raise.
    assert service.request_recapture("kiosk3-elec").status == "queued"
    assert service.request_recapture("ghost-meter").status == "unknown_device"


def test_unknown_ids_raise_not_found(seeded_session: Session) -> None:
    # WHY: reads on an unknown id fail loudly so the adapter can map to HTTP 404.
    with pytest.raises(service.NotFoundError):
        service.query_readings("ghost-meter")
    with pytest.raises(service.NotFoundError):
        service.compute_invoice("room99")


def test_anomaly_is_deterministic_english(seeded_session: Session) -> None:
    # WHY: beat #2 needs zero network — the 4× is computed by code (_detect_spike), and the
    # English names that same factor, so nothing can drift between the number and the prose.
    anomaly = service.explain_anomaly("kiosk3-elec")
    assert anomaly.has_anomaly is True
    assert anomaly.factor == 4.0
    assert anomaly.explanation  # deterministic English
    assert "4" in anomaly.explanation  # the prose names the code-computed factor


def _params(fn: Callable[..., object]) -> list[tuple[str, object]]:
    return [(p.name, p.default) for p in inspect.signature(fn).parameters.values()]


def test_contract_models_unchanged() -> None:
    # WHY: FROZEN-CONTRACT invariant — return type AND signature byte-identical to Phase 0,
    # so an accidental arg (e.g. a stray `session` kwarg) or a swapped model trips this.
    empty = inspect.Parameter.empty
    returns = {
        service.query_readings: contract.ReadingsSummary,
        service.explain_anomaly: contract.AnomalyExplanation,
        service.list_unpaid: contract.UnpaidList,
        service.compute_invoice: contract.Invoice,
        service.request_recapture: contract.RecaptureAck,
    }
    for fn, model in returns.items():
        assert inspect.signature(fn).return_annotation is model

    assert _params(service.query_readings) == [
        ("device_id", empty),
        ("period", "2026-07"),
    ]
    assert _params(service.explain_anomaly) == [("device_id", empty)]
    assert _params(service.list_unpaid) == [("period", "2026-07")]
    assert _params(service.compute_invoice) == [
        ("tenant_id", empty),
        ("period", "2026-07"),
    ]
    assert _params(service.request_recapture) == [("device_id", empty)]


def test_dashboard_overview_composes_the_five_beats(seeded_session: Session) -> None:
    # WHY: the dashboard renders this one payload — if it drifts, every panel lies.
    # It must carry the same Core numbers the voice bot answers with, not a copy.
    overview = service.dashboard_overview()

    # beat #4 — invoice amounts are usage × tariff (18×15000, 620×3000)
    assert overview.invoices["room2"].amount == pytest.approx(270_000, abs=1e-3)
    assert overview.invoices["room3"].amount == pytest.approx(1_860_000, abs=1e-3)

    # beat #3 — room2 + room3 unpaid, room1 paid (the card badge derives from this)
    unpaid_ids = {tenant.tenant_id for tenant in overview.unpaid.tenants}
    assert unpaid_ids == {"room2", "room3"}
    paid = {card.tenant_id: card.paid for card in overview.devices}
    assert paid == {"room1": True, "room2": False, "room3": False}

    # beat #2 — kiosk3 flagged, and its series still carries the 4× spike day
    assert "kiosk3-elec" in overview.anomalies
    series = overview.readings["kiosk3-elec"].series
    spike = max(point.value for point in series)
    baseline = sorted(point.value for point in series)[len(series) // 2]  # median-ish
    assert spike >= 3 * baseline
