"""FROZEN Core API seam — the contract both tracks bind to.

5 tool signatures + 7 return models. Track B's MCP wiring and Track A's
dashboard both bind to exactly these field names; later real-Core work changes
only `service.py`, never this file.
"""

from typing import Literal

from pydantic import BaseModel

CURRENCY = "VND"
MeterType = Literal["water", "elec"]
Unit = Literal["m3", "kWh"]


class ReadingPoint(BaseModel):
    timestamp: str  # ISO local, jomjol style "%Y-%m-%dT%H:%M:%S"
    value: float


class ReadingsSummary(BaseModel):
    device_id: str
    meter_type: MeterType
    unit: Unit
    period: str  # "2026-07"
    usage: float  # consumption over the period
    latest_value: float
    latest_timestamp: str
    series: list[ReadingPoint]


class AnomalyExplanation(BaseModel):
    device_id: str
    has_anomaly: bool
    kind: str | None  # "spike"
    detected_at: str | None  # "2026-07-14"
    factor: float | None  # 4.0
    explanation: (
        str  # plain-language English. Stub = canned; real = an LLM inside the tool.
    )


class UnpaidTenant(BaseModel):
    tenant_id: str
    room: str
    name: str
    amount_due: float
    currency: str = CURRENCY
    invoice_id: str


class UnpaidList(BaseModel):
    period: str
    count: int
    tenants: list[UnpaidTenant]


class Invoice(BaseModel):
    invoice_id: str
    tenant_id: str
    room: str
    device_id: str
    meter_type: MeterType
    period: str
    usage: float
    unit: Unit
    tariff_rate: float
    amount: float  # usage * tariff_rate
    currency: str = CURRENCY
    paid: bool


class RecaptureAck(BaseModel):
    device_id: str
    status: Literal["queued", "unknown_device"]
    message: str
