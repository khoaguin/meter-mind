"""Stub Core implementation — the only place demo logic lives.

Loads + validates `seed.yaml` into `SeedData` at import (fail-fast), then the 5
tool fns query it and compute derived values in code (`amount = usage × tariff`,
the synthetic reading series). `api.py` / `mcp_server.py` are thin adapters over
these fns. Later real-Core work (Phase 2) rebinds these fns to the DB; the
contract and adapters do not change.

`SeedData` and `SEED_PATH` are the Phase-0 boundary reused by the DB seed loader
(`hub.db.seed_loader`) — a malformed `seed.yaml` errors as a `ValidationError`
here, before anything downstream reads it.
"""

import calendar
from pathlib import Path

import yaml
from pydantic import BaseModel

from hub.core.contract import (
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

SEED_PATH: Path = Path(__file__).parent / "seed.yaml"


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


SEED: SeedData = load_seed_data()  # fail-fast at import


# --- Derivation helpers ---------------------------------------------------------


def days_in_period(period: str) -> int:
    """Calendar days in a "YYYY-MM" period (2026-07 -> 31)."""
    year, month = (int(part) for part in period.split("-"))
    return calendar.monthrange(year, month)[1]


def _account_for_device(device_id: str) -> SeedAccount:
    for account in SEED.accounts:
        if account.device_id == device_id:
            return account
    raise NotFoundError(f"unknown device_id: {device_id}")


def _account_for_tenant(tenant_id: str) -> SeedAccount:
    for account in SEED.accounts:
        if account.tenant_id == tenant_id:
            return account
    raise NotFoundError(f"unknown tenant_id: {tenant_id}")


def _invoice_id(period: str, tenant_id: str) -> str:
    return f"INV-{period}-{tenant_id}"


def _amount(account: SeedAccount) -> float:
    return account.usage * SEED.tariffs[account.meter_type]


def _synth_series(account: SeedAccount, period: str) -> list[ReadingPoint]:
    """Per-day consumption points: flat baseline, one `factor`× spike on the anomaly day.

    baseline b solves (N - 1 + factor) * b == usage so the series reconciles to
    the seed usage total; non-anomaly devices are flat (b = usage / N).
    """
    n = days_in_period(period)
    is_anomaly = SEED.anomaly.device_id == account.device_id
    factor = SEED.anomaly.factor if is_anomaly else None
    spike_day = int(SEED.anomaly.detected_at.split("-")[2]) if is_anomaly else None
    baseline = account.usage / ((n - 1 + factor) if factor else n)
    points: list[ReadingPoint] = []
    for day in range(1, n + 1):
        value = baseline * factor if (factor and day == spike_day) else baseline
        points.append(
            ReadingPoint(timestamp=f"{period}-{day:02d}T00:00:00", value=value)
        )
    return points


# --- The 5 frozen tools ---------------------------------------------------------


def query_readings(device_id: str, period: str = "2026-07") -> ReadingsSummary:
    """Usage summary + per-day series for a meter over a billing period (beat #1)."""
    account = _account_for_device(device_id)
    series = _synth_series(account, period)
    return ReadingsSummary(
        device_id=device_id,
        meter_type=account.meter_type,
        unit=account.unit,
        period=period,
        usage=account.usage,  # seed fact, not the float-summed series
        latest_value=account.usage,  # cumulative face from START 0 == total (stub)
        latest_timestamp=series[-1].timestamp,
        series=series,
    )


def explain_anomaly(device_id: str) -> AnomalyExplanation:
    """Why a meter spiked — canned VN string in the stub, Claude at runtime later (beat #2)."""
    _account_for_device(device_id)  # validate the device exists
    anomaly = SEED.anomaly
    if anomaly.device_id == device_id:
        return AnomalyExplanation(
            device_id=device_id,
            has_anomaly=True,
            kind=anomaly.kind,
            detected_at=anomaly.detected_at,
            factor=anomaly.factor,
            explanation=anomaly.explanation,
        )
    return AnomalyExplanation(
        device_id=device_id,
        has_anomaly=False,
        kind=None,
        detected_at=None,
        factor=None,
        explanation="Không phát hiện bất thường.",
    )


def list_unpaid(period: str = "2026-07") -> UnpaidList:
    """Tenants with an outstanding bill this period (beat #3)."""
    tenants = [
        UnpaidTenant(
            tenant_id=account.tenant_id,
            room=account.room,
            name=account.name,
            amount_due=_amount(account),
            invoice_id=_invoice_id(period, account.tenant_id),
        )
        for account in SEED.accounts
        if not account.paid
    ]
    return UnpaidList(period=period, count=len(tenants), tenants=tenants)


def compute_invoice(tenant_id: str, period: str = "2026-07") -> Invoice:
    """One tenant's invoice with the amount derived from usage × tariff (beat #4)."""
    account = _account_for_tenant(tenant_id)
    rate = SEED.tariffs[account.meter_type]
    return Invoice(
        invoice_id=_invoice_id(period, tenant_id),
        tenant_id=tenant_id,
        room=account.room,
        device_id=account.device_id,
        meter_type=account.meter_type,
        period=period,
        usage=account.usage,
        unit=account.unit,
        tariff_rate=rate,
        amount=account.usage * rate,
        paid=account.paid,
    )


def request_recapture(device_id: str) -> RecaptureAck:
    """Queue a fresh capture for a device; unknown device -> a soft ack, not a 404 (beat #5)."""
    known = any(account.device_id == device_id for account in SEED.accounts)
    if known:
        return RecaptureAck(
            device_id=device_id,
            status="queued",
            message=f"Đã xếp hàng chụp lại {device_id}.",
        )
    return RecaptureAck(
        device_id=device_id,
        status="unknown_device",
        message=f"Không tìm thấy thiết bị {device_id}.",
    )


def list_devices() -> list[dict[str, str]]:
    """Seed devices for the dashboard's device picker (not part of the frozen 5 tools)."""
    return [
        {
            "device_id": account.device_id,
            "meter_type": account.meter_type,
            "unit": account.unit,
            "tenant_id": account.tenant_id,
            "room": account.room,
        }
        for account in SEED.accounts
    ]
