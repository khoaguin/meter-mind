import asyncio
from collections.abc import Callable
from typing import Protocol

import yaml
from pydantic import BaseModel

from edgesim.contract import Reading, Topics
from edgesim.device import DeviceConfig, VirtualDevice
from edgesim.imagery import CropBank
from edgesim.publisher import Publisher
from edgesim.reader import DigitReader
from edgesim.scenarios import make_scenario


class PublisherLike(Protocol):
    """Subset of the Publisher surface the fleet loop uses (test-injectable)."""

    def connect(self) -> None: ...

    def publish_reading(
        self, topics: Topics, reading: Reading, confidence: float, meter_type: str
    ) -> list[tuple[str, str]]: ...


class FleetDeviceSpec(BaseModel):
    device_id: str
    main_topic: str
    meter_type: str
    n_digits: int
    decimals: int
    start_value: float
    scenario: str
    group: str = "main"


class FleetConfig(BaseModel):
    broker_host: str
    broker_port: int = 1883
    interval_seconds: float = 5.0
    model_path: str
    digits_dir: str
    devices: list[FleetDeviceSpec]


def load_fleet(path: str) -> FleetConfig:
    with open(path) as f:
        return FleetConfig(**yaml.safe_load(f))


async def run_fleet(
    cfg: FleetConfig,
    max_ticks: int | None = None,
    publisher_factory: Callable[..., PublisherLike] = Publisher,
    now_fn: Callable[[], str] | None = None,
) -> None:
    if now_fn is None:
        from datetime import datetime

        now_fn = lambda: datetime.now().strftime("%Y-%m-%dT%H:%M:%S")  # noqa: E731

    reader = DigitReader(cfg.model_path)
    bank = CropBank(cfg.digits_dir)
    devices = []
    for i, spec in enumerate(cfg.devices):
        dev_cfg = DeviceConfig(**spec.model_dump(exclude={"scenario"}))
        devices.append(
            (
                VirtualDevice(dev_cfg, reader, bank),
                make_scenario(spec.scenario, seed=i),
                Topics(spec.main_topic, spec.group),
            )
        )

    pub = publisher_factory(cfg.broker_host, cfg.broker_port)
    pub.connect()

    tick = 0
    while max_ticks is None or tick < max_ticks:
        for dev, scenario, topics in devices:
            t = scenario(tick)
            res = dev.step(t.delta, t.rolling, now_fn())
            pub.publish_reading(topics, res.reading, res.confidence, res.meter_type)
        tick += 1
        if max_ticks is None or tick < max_ticks:
            await asyncio.sleep(cfg.interval_seconds)
