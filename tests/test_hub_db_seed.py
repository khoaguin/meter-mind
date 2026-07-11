"""DB seed loader — each test names the invariant + the demo beat it defends.

The `Reading` series is the only DB source for beat #1's total and beat #2's
re-derived anomaly facts, so these tests guard the seed->series->re-derive
round-trip Phase 2's tools depend on.
"""

import statistics
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlmodel import Session, func, select

from hub.db.models import Device, Invoice, Reading, Tariff, Tenant
from hub.db.seed_loader import START_VALUE, load_seed

TABLES = [Device, Tenant, Tariff, Reading, Invoice]


def _count(session: Session, model: type) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def _ordered_readings(session: Session, device_id: str) -> list[Reading]:
    stmt = (
        select(Reading)
        .where(Reading.device_id == device_id)
        .order_by(Reading.timestamp)
    )
    return list(session.exec(stmt))


def _daily_deltas(session: Session, device_id: str) -> list[tuple[str, float]]:
    """(date, consumption) per day: diffs of the cumulative face, prepended with START_VALUE."""
    rows = _ordered_readings(session, device_id)
    prev = START_VALUE
    out: list[tuple[str, float]] = []
    for row in rows:
        out.append((row.timestamp[:10], row.value - prev))
        prev = row.value
    return out


def test_seed_is_idempotent(seeded_session: Session) -> None:
    # WHY: seed can be re-run mid-demo without corrupting state — row counts must be stable.
    before = {model.__name__: _count(seeded_session, model) for model in TABLES}
    load_seed(seeded_session)  # second run over the same DB
    after = {model.__name__: _count(seeded_session, model) for model in TABLES}
    assert before == after
    assert before["Reading"] == 7 * 31  # 7 devices × 31 days in 2026-07


def test_kiosk3_series_sums_to_usage(seeded_session: Session) -> None:
    # WHY: beat #1 total must match the chart; float rounding of 30·b + 4·b won't land on 620.0.
    deltas = [value for _, value in _daily_deltas(seeded_session, "kiosk3-elec")]
    assert sum(deltas) == pytest.approx(620, abs=1e-6)


def test_spike_day_is_4x(seeded_session: Session) -> None:
    # WHY: beat #2 money shot — exactly what Phase 2's explain_anomaly re-derives from the series.
    deltas = _daily_deltas(seeded_session, "kiosk3-elec")
    spike_date, spike_value = max(deltas, key=lambda pair: pair[1])
    baseline = [value for date, value in deltas if date != spike_date]
    assert spike_date == "2026-07-14"
    assert round(spike_value / statistics.median(baseline)) == 4


def test_water_series_organic_no_false_spike(seeded_session: Session) -> None:
    # WHY: non-anomaly meters vary day-to-day (a realistic chart, not a dead-flat line)
    # but must NOT trip the detector — sum == usage, all deltas positive, and the biggest
    # day stays well under the 3× spike threshold so explain_anomaly reports no anomaly.
    deltas = [value for _, value in _daily_deltas(seeded_session, "kiosk1-water")]
    assert sum(deltas) == pytest.approx(12, abs=1e-6)
    assert min(deltas) > 0  # consumption never goes negative
    assert max(deltas) != min(deltas)  # organic wiggle, not flat
    baseline = sorted(deltas)[:-1]  # drop the max, like the detector's baseline
    assert max(deltas) / statistics.median(baseline) < 3.0  # no false spike


def test_unpaid_invoices(seeded_session: Session) -> None:
    # WHY: beats #3/#4 — paid = room1/room4/room5; unpaid = room2/room3/room6/room7.
    paid = {inv.tenant_id: inv.paid for inv in seeded_session.exec(select(Invoice))}
    assert paid == {
        "room1": True,
        "room2": False,
        "room3": False,
        "room4": True,
        "room5": True,
        "room6": False,
        "room7": False,
    }


def test_tariffs_present(seeded_session: Session) -> None:
    # WHY: beat #4 amount is derived from these rates.
    rates = {t.meter_type: t.rate for t in seeded_session.exec(select(Tariff))}
    assert rates == {"water": 15000, "elec": 3000}


def test_malformed_seed_fails_loud(seeded_session: Session, tmp_path: Path) -> None:
    # WHY: fail-fast at the boundary — never a half-populated DB.
    before = {model.__name__: _count(seeded_session, model) for model in TABLES}
    bad = tmp_path / "bad.yaml"
    bad.write_text("period: 2026-07\naccounts: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_seed(seeded_session, bad)
    after = {model.__name__: _count(seeded_session, model) for model in TABLES}
    assert before == after  # DB untouched
