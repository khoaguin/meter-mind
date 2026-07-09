"""SQLModel tables for the hub store — dimensions + the time-series `Reading`.

Reuses the FROZEN `MeterType` / `Unit` Literals from `core.contract` (do not
redefine). Derived values (`amount`, `usage`) are NOT stored — they stay derived
in code so editing a tariff can't silently desync a stale literal.
"""

from datetime import datetime

from sqlmodel import AutoString, Field, SQLModel

from hub.core.contract import MeterType, Unit  # FROZEN Literals


class Device(SQLModel, table=True):
    device_id: str = Field(primary_key=True)  # "kiosk3-elec"
    # Keep the FROZEN Literals for validation; SQLModel can't infer a column type
    # from a Literal, so pin the SQL column to TEXT (AutoString) explicitly.
    meter_type: MeterType = Field(sa_type=AutoString)  # "water" | "elec"
    unit: Unit = Field(sa_type=AutoString)  # "m3" | "kWh"
    group: str = "main"


class Tenant(SQLModel, table=True):
    tenant_id: str = Field(primary_key=True)  # "room3"
    room: str  # "Room 3" — the only `room`, sourced from seed accounts
    name: str
    device_id: str = Field(foreign_key="device.device_id")


class Tariff(SQLModel, table=True):
    meter_type: str = Field(primary_key=True)  # "water" | "elec"
    rate: float  # VND per m3 / kWh


class Reading(SQLModel, table=True):  # TIME-SERIES
    id: int | None = Field(default=None, primary_key=True)
    device_id: str = Field(foreign_key="device.device_id", index=True)
    timestamp: str  # jomjol local "%Y-%m-%dT%H:%M:%S"
    value: float  # cumulative meter face
    received_at: datetime  # hub receipt time (never trust embedded local ts as UTC)


class Invoice(SQLModel, table=True):
    invoice_id: str = Field(primary_key=True)  # synth: f"INV-{period}-{tenant_id}"
    tenant_id: str = Field(foreign_key="tenant.tenant_id")
    period: str  # "2026-07"
    paid: bool
    paid_at: datetime | None = None
