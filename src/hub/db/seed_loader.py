"""Idempotent seed loader: seed.yaml -> real SQLite rows.

Parses `seed.yaml` at the Phase-0 boundary (`SeedData`, fail-fast), upserts the
dimension rows, and synthesizes the daily `Reading` series (flat baseline + a
`factor`× spike on the anomaly day) so `sum(daily deltas) == account.usage`.
Re-running converges (merge dimensions by PK; delete-then-insert the seeded
period's readings). Run: `just hub-seed` / `python -m hub.db.seed_loader`.
"""

from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlmodel import Session, col, delete

from hub.core.service import (
    SEED_PATH,
    SeedAccount,
    SeedAnomaly,
    SeedData,
    days_in_period,
    load_seed_data,
)
from hub.db.models import Device, Invoice, Reading, Tariff, Tenant
from hub.db.session import engine, init_db

START_VALUE: float = 0.0  # loader-local cumulative base — NOT a seed field
SYNTH_RECEIVED_AT: datetime = datetime(
    2026, 8, 1
)  # deterministic synthetic hub receipt time


def _synth_series(
    account: SeedAccount, anomaly: SeedAnomaly, period: str
) -> list[Reading]:
    """Cumulative daily meter face from START_VALUE; inject a `factor`× day on
    anomaly.detected_at for the anomaly device so sum(daily deltas) == account.usage."""
    n = days_in_period(period)
    is_anomaly = anomaly.device_id == account.device_id
    factor = anomaly.factor if is_anomaly else None
    spike_day = int(anomaly.detected_at.split("-")[2]) if is_anomaly else None
    denom = (n - 1 + factor) if factor else float(n)
    assert denom != 0, f"degenerate period {period!r}: N-1+factor == 0"
    baseline = account.usage / denom
    rows: list[Reading] = []
    face = START_VALUE
    for day in range(1, n + 1):
        delta = baseline * factor if (factor and day == spike_day) else baseline
        face += delta
        rows.append(
            Reading(
                device_id=account.device_id,
                timestamp=f"{period}-{day:02d}T00:00:00",
                value=face,
                received_at=SYNTH_RECEIVED_AT,
            )
        )
    if is_anomaly:
        logger.info(
            "synth: injected {factor}× spike on {detected_at} for {device_id}",
            factor=factor,
            detected_at=anomaly.detected_at,
            device_id=account.device_id,
        )
    return rows


def load_seed(session: Session, seed_path: Path = SEED_PATH) -> None:
    """Parse seed.yaml -> SeedData (fail-fast), upsert dimension rows, synth Readings, commit."""
    seed: SeedData = load_seed_data(seed_path)  # ValidationError here, before any write
    period = seed.period

    # Dimension rows, FK-safe order: Device -> Tenant -> Tariff -> Invoice (upsert by PK).
    for account in seed.accounts:
        session.merge(
            Device(
                device_id=account.device_id,
                meter_type=account.meter_type,
                unit=account.unit,
            )
        )
    for account in seed.accounts:
        session.merge(
            Tenant(
                tenant_id=account.tenant_id,
                room=account.room,
                name=account.name,
                device_id=account.device_id,
            )
        )
    for meter_type, rate in seed.tariffs.items():
        session.merge(Tariff(meter_type=meter_type, rate=rate))
    for account in seed.accounts:
        session.merge(
            Invoice(
                invoice_id=f"INV-{period}-{account.tenant_id}",
                tenant_id=account.tenant_id,
                period=period,
                paid=account.paid,
                paid_at=SYNTH_RECEIVED_AT if account.paid else None,
            )
        )

    # Readings have an auto-int PK (no natural key): delete-then-insert this period per device.
    for account in seed.accounts:
        session.exec(
            delete(Reading).where(
                col(Reading.device_id) == account.device_id,
                col(Reading.timestamp).startswith(period),
            )
        )
        session.add_all(_synth_series(account, seed.anomaly, period))

    session.commit()  # the ONE commit


if __name__ == "__main__":  # `python -m hub.db.seed_loader`
    init_db()
    with Session(engine) as session:  # single context manager; load_seed commits once
        load_seed(session)
