import random

from pydantic import BaseModel

from edgesim.assemble import assemble
from edgesim.contract import Reading
from edgesim.imagery import CropBank, render_strip, split_strip
from edgesim.reader import DigitReader


class DeviceConfig(BaseModel):
    device_id: str
    main_topic: str
    meter_type: str
    n_digits: int
    decimals: int
    start_value: float
    group: str = "main"


class DeviceState(BaseModel):
    value: float
    pre_value: float
    rolling: bool = False


class StepResult(BaseModel):
    reading: Reading
    confidence: float
    meter_type: str


class VirtualDevice:
    def __init__(self, cfg: DeviceConfig, reader: DigitReader, bank: CropBank) -> None:
        self.cfg = cfg
        self._reader = reader
        self._bank = bank
        self.state = DeviceState(value=cfg.start_value, pre_value=cfg.start_value)

    def value_digits(self) -> str:
        scaled = round(self.state.value * (10**self.cfg.decimals))
        return str(scaled).zfill(self.cfg.n_digits)[-self.cfg.n_digits :]

    def _fmt(self, value: float) -> str:
        return f"{value:.{self.cfg.decimals}f}"

    def step(self, delta: float, rolling: bool, now: str) -> StepResult:
        self.state.pre_value = self.state.value
        self.state.value += delta
        digits = self.value_digits()
        rolling_index = random.randint(0, self.cfg.n_digits - 1) if rolling else None
        strip = render_strip(digits, self._bank, rolling_index=rolling_index)
        preds = [
            self._reader.predict_crop(c) for c in split_strip(strip, self.cfg.n_digits)
        ]
        result = assemble(preds, self.cfg.decimals, self._fmt(self.state.pre_value))
        if result.has_nan:
            self.state.value = self.state.pre_value  # hold last good
            rate = 0.0
        else:
            rate = self.state.value - self.state.pre_value
        reading = Reading(
            value=result.value,
            raw=self._fmt(self.state.value),
            pre=self._fmt(self.state.pre_value),
            error=result.error,
            rate=f"{rate:.6f}",
            timestamp=now,
        )
        return StepResult(
            reading=reading,
            confidence=result.confidence,
            meter_type=self.cfg.meter_type,
        )
