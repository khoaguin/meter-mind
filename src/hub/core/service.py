"""Real Core — the 5 frozen tools, now answering from the DB (Phase 2).

The signatures are FROZEN (byte-identical to the Phase-0 stub): no `session`
param, no new kwargs. Each fn opens its own `Session` on the module-level engine
in `hub.db.session` (acquired internally, never injected), reads the Phase-1
tables, and derives everything in deterministic code — `amount = usage × tariff`,
the per-day series, the spike detector, and the anomaly explanation. No model runs
in the hub: Agora's My Bot does the routing/phrasing; every tool here is arithmetic.

`SeedData` / `SEED_PATH` / `load_seed_data` / `days_in_period` stay here as the
Phase-0 boundary reused by `hub.db.seed_loader` — they no longer feed the tools.
"""

import calendar
import statistics
from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel
from sqlmodel import Session, col, select

from hub.core.contract import (
    CURRENCY,
    AnomalyExplanation,
    Invoice,
    MeterType,
    ReadingPoint,
    ReadingsSummary,
    RecaptureAck,
    Unit,
    UnpaidList,
    UnpaidTenant,
)
from hub.db import session as db_session
from hub.db.models import Device, Reading, Tariff, Tenant
from hub.db.models import Invoice as InvoiceRow

SEED_PATH: Path = Path(__file__).parent / "seed.yaml"
DEFAULT_PERIOD: str = "2026-07"  # single demo period (multi-period is out of scope)
PERIOD_OPENING_FACE: float = (
    0.0  # meter face at period start — matches the seed START_VALUE
)
SPIKE_FACTOR_THRESHOLD: float = (
    3.0  # seed lands 4.0; threshold < seed so the spike trips
)


class NotFoundError(Exception):
    """Unknown device_id / tenant_id — adapters map this to HTTP 404 / MCP tool error."""


# --- Seed boundary model (Phase-0 freeze; reused by hub.db.seed_loader) ---------


class SeedAccount(BaseModel):
    tenant_id: str
    room: str
    name: str
    device_id: str
    meter_type: MeterType
    unit: Unit
    usage: float
    paid: bool


class SeedAnomaly(BaseModel):
    device_id: str
    kind: str
    detected_at: str  # "2026-07-14"
    factor: float
    explanation: str


class SeedData(BaseModel):
    currency: str
    period: str
    tariffs: dict[str, float]  # {"water": 15000, "elec": 3000}
    accounts: list[SeedAccount]
    anomaly: SeedAnomaly


def load_seed_data(path: Path = SEED_PATH) -> SeedData:
    """Parse + validate seed.yaml at the boundary; malformed file -> ValidationError."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeedData.model_validate(raw)


def days_in_period(period: str) -> int:
    """Calendar days in a "YYYY-MM" period (2026-07 -> 31). Reused by the seed loader."""
    year, month = (int(part) for part in period.split("-"))
    return calendar.monthrange(year, month)[1]


# --- DB read + derivation helpers (deterministic, no model calls) ---------------


def _period_readings(
    session: Session, device_id: str, period: str
) -> Sequence[Reading]:
    stmt = (
        select(Reading)
        .where(
            col(Reading.device_id) == device_id,
            col(Reading.timestamp).startswith(period),
        )
        .order_by(col(Reading.timestamp))
    )
    return session.exec(stmt).all()


def _daily_series(readings: Sequence[Reading]) -> list[ReadingPoint]:
    """Cumulative meter faces -> per-day consumption deltas.

    The first day's delta is measured against `PERIOD_OPENING_FACE` (the meter
    face at period start), so `Σ(series.value) == last_face - opening == usage`.
    """
    points: list[ReadingPoint] = []
    prev = PERIOD_OPENING_FACE
    for reading in readings:
        points.append(
            ReadingPoint(timestamp=reading.timestamp, value=reading.value - prev)
        )
        prev = reading.value
    return points


def _period_usage(session: Session, device_id: str, period: str) -> float:
    readings = _period_readings(session, device_id, period)
    if not readings:
        return 0.0
    return readings[-1].value - PERIOD_OPENING_FACE


def _tariff_rate(session: Session, meter_type: str) -> float:
    tariff = session.get(Tariff, meter_type)
    if tariff is None:
        raise NotFoundError(f"no tariff for meter_type: {meter_type}")
    return tariff.rate


def _detect_spike(series: list[ReadingPoint]) -> tuple[str, str, float] | None:
    """Deterministic threshold detector over the per-day series -> (kind, date, factor) | None.

    factor = max_day_delta / median(baseline deltas), baseline = every day except the max.
    Short/empty series (< 2 days) or a zero baseline -> None (no divide-by-zero).
    """
    if len(series) < 2:
        return None
    values = [point.value for point in series]
    max_idx = max(range(len(values)), key=values.__getitem__)
    baseline = [value for index, value in enumerate(values) if index != max_idx]
    median_baseline = statistics.median(baseline)
    if median_baseline == 0:
        return None
    factor = values[max_idx] / median_baseline
    if factor < SPIKE_FACTOR_THRESHOLD:
        return None
    return ("spike", series[max_idx].timestamp[:10], round(factor, 1))


# --- The 5 frozen tools (DB-backed) ---------------------------------------------


def query_readings(device_id: str, period: str = "2026-07") -> ReadingsSummary:
    """Usage summary + per-day series for a meter over a billing period (beat #1)."""
    with Session(db_session.engine) as session:
        device = session.get(Device, device_id)
        if device is None:
            raise NotFoundError(f"unknown device_id: {device_id}")
        readings = _period_readings(session, device_id, period)
        series = _daily_series(readings)
        usage = sum(point.value for point in series)
        return ReadingsSummary(
            device_id=device_id,
            meter_type=device.meter_type,
            unit=device.unit,
            period=period,
            usage=usage,
            latest_value=PERIOD_OPENING_FACE + usage,  # cumulative face at period end
            latest_timestamp=readings[-1].timestamp if readings else "",
            series=series,
        )


def _anomaly_prose(kind: str, detected_at: str, factor: float) -> str:
    """Deterministic English for beat #2 — code owns the number, no model in the loop."""
    return (
        f"Detected {kind}: usage rose about {factor:g} times on {detected_at} compared with "
        "normal days — likely a leak or a faulty meter."
    )


def explain_anomaly(device_id: str) -> AnomalyExplanation:
    """Why a meter spiked — deterministic detector + deterministic English prose (beat #2)."""
    with Session(db_session.engine) as session:
        device = session.get(Device, device_id)
        if device is None:
            raise NotFoundError(f"unknown device_id: {device_id}")
        series = _daily_series(_period_readings(session, device_id, DEFAULT_PERIOD))

    spike = _detect_spike(series)
    if spike is None:
        return AnomalyExplanation(
            device_id=device_id,
            has_anomaly=False,
            kind=None,
            detected_at=None,
            factor=None,
            explanation="No anomaly detected.",
        )

    kind, detected_at, factor = spike
    explanation = _anomaly_prose(kind, detected_at, factor)
    return AnomalyExplanation(
        device_id=device_id,
        has_anomaly=True,
        kind=kind,
        detected_at=detected_at,
        factor=factor,
        explanation=explanation,
    )


def list_unpaid(period: str = "2026-07") -> UnpaidList:
    """Tenants with an outstanding bill this period (beat #3)."""
    with Session(db_session.engine) as session:
        unpaid_rows = session.exec(
            select(InvoiceRow).where(
                col(InvoiceRow.paid).is_(False), col(InvoiceRow.period) == period
            )
        ).all()
        tenants: list[UnpaidTenant] = []
        for invoice in unpaid_rows:
            tenant = session.get(Tenant, invoice.tenant_id)
            if tenant is None:
                continue
            device = session.get(Device, tenant.device_id)
            usage = _period_usage(session, tenant.device_id, period)
            rate = _tariff_rate(session, device.meter_type) if device else 0.0
            tenants.append(
                UnpaidTenant(
                    tenant_id=tenant.tenant_id,
                    room=tenant.room,
                    name=tenant.name,
                    amount_due=usage * rate,
                    invoice_id=invoice.invoice_id,
                )
            )
    return UnpaidList(period=period, count=len(tenants), tenants=tenants)


def compute_invoice(tenant_id: str, period: str = "2026-07") -> Invoice:
    """One tenant's invoice with the amount derived from usage × tariff (beat #4)."""
    with Session(db_session.engine) as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise NotFoundError(f"unknown tenant_id: {tenant_id}")
        device = session.get(Device, tenant.device_id)
        if device is None:
            raise NotFoundError(
                f"tenant {tenant_id} references unknown device {tenant.device_id}"
            )
        usage = _period_usage(session, tenant.device_id, period)
        rate = _tariff_rate(session, device.meter_type)
        invoice = session.exec(
            select(InvoiceRow).where(
                col(InvoiceRow.tenant_id) == tenant_id, col(InvoiceRow.period) == period
            )
        ).first()
        return Invoice(
            invoice_id=invoice.invoice_id if invoice else f"INV-{period}-{tenant_id}",
            tenant_id=tenant_id,
            room=tenant.room,
            device_id=tenant.device_id,
            meter_type=device.meter_type,
            period=period,
            usage=usage,
            unit=device.unit,
            tariff_rate=rate,
            amount=usage * rate,
            paid=invoice.paid if invoice else False,
        )


def request_recapture(device_id: str) -> RecaptureAck:
    """Queue a fresh capture for a device; unknown device -> a soft ack, not a 404 (beat #5)."""
    with Session(db_session.engine) as session:
        known = session.get(Device, device_id) is not None
    if known:
        return RecaptureAck(
            device_id=device_id,
            status="queued",
            message=f"Recapture queued for {device_id}.",
        )
    return RecaptureAck(
        device_id=device_id,
        status="unknown_device",
        message=f"Unknown device {device_id}.",
    )


def list_devices() -> list[dict[str, str]]:
    """Seed devices for the dashboard's device picker (not part of the frozen 5 tools)."""
    with Session(db_session.engine) as session:
        tenants = {
            tenant.device_id: tenant for tenant in session.exec(select(Tenant)).all()
        }
        devices = session.exec(select(Device)).all()
        result: list[dict[str, str]] = []
        for device in devices:
            tenant = tenants.get(device.device_id)
            result.append(
                {
                    "device_id": device.device_id,
                    "meter_type": device.meter_type,
                    "unit": device.unit,
                    "tenant_id": tenant.tenant_id if tenant else "",
                    "room": tenant.room if tenant else "",
                    "name": tenant.name if tenant else "",
                }
            )
    return result


class DeviceCard(BaseModel):
    """One device row on the dashboard — device + tenant + the derived usage/amount/paid."""

    device_id: str
    tenant_id: str
    room: str
    name: str
    meter_type: MeterType
    unit: Unit
    usage: float
    latest_value: float
    paid: bool
    amount: float | None  # None when a device has no tenant
    has_anomaly: bool


class DashboardOverview(BaseModel):
    """The whole owner-dashboard payload in one validated model — the page fetches this once.

    NOT a frozen tool (a dashboard convenience, like `list_devices`), but still a
    Pydantic model at the boundary: it's what crosses service -> HTTP -> browser.
    Reuses the frozen models so it can never drift from the voice answers.
    """

    period: str
    currency: str
    devices: list[DeviceCard]
    unpaid: UnpaidList
    readings: dict[str, ReadingsSummary]
    anomalies: dict[str, AnomalyExplanation]
    invoices: dict[str, Invoice]


def dashboard_overview(period: str = DEFAULT_PERIOD) -> DashboardOverview:
    """Compose the frozen tools into the one payload the dashboard renders.

    No model, no new arithmetic: every number already came from `query_readings`
    / `explain_anomaly` / `list_unpaid` / `compute_invoice` above.
    """
    unpaid = list_unpaid(period)
    unpaid_ids = {tenant.tenant_id for tenant in unpaid.tenants}
    cards: list[DeviceCard] = []
    readings: dict[str, ReadingsSummary] = {}
    anomalies: dict[str, AnomalyExplanation] = {}
    invoices: dict[str, Invoice] = {}
    for device in list_devices():
        device_id = device["device_id"]
        tenant_id = device["tenant_id"]
        summary = query_readings(device_id, period)
        readings[device_id] = summary
        anomaly = explain_anomaly(device_id)
        if anomaly.has_anomaly:
            anomalies[device_id] = anomaly
        amount: float | None = None
        if tenant_id:
            invoice = compute_invoice(tenant_id, period)
            invoices[tenant_id] = invoice
            amount = invoice.amount
        cards.append(
            DeviceCard(
                device_id=device_id,
                tenant_id=tenant_id,
                room=device["room"],
                name=device["name"],
                meter_type=summary.meter_type,
                unit=summary.unit,
                usage=summary.usage,
                latest_value=summary.latest_value,
                paid=tenant_id not in unpaid_ids if tenant_id else True,
                amount=amount,
                has_anomaly=anomaly.has_anomaly,
            )
        )
    return DashboardOverview(
        period=period,
        currency=CURRENCY,
        devices=cards,
        unpaid=unpaid,
        readings=readings,
        anomalies=anomalies,
        invoices=invoices,
    )
