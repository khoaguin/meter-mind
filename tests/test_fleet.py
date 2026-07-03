import asyncio

from edgesim.fleet import FleetConfig, FleetDeviceSpec, run_fleet


class RecordingPublisher:
    def __init__(self, *_a, **_k):
        self.readings = []

    def connect(self):
        pass

    def publish_reading(self, topics, reading, confidence, meter_type):
        self.readings.append((topics.main_topic, reading.value))
        return []

    def publish_status(self, *a, **k):
        pass


def test_run_fleet_steps_all_devices(digits_dir, model_path):
    rec = RecordingPublisher()
    cfg = FleetConfig(
        broker_host="x",
        interval_seconds=0.0,
        model_path=str(model_path),
        digits_dir=str(digits_dir),
        devices=[
            FleetDeviceSpec(
                device_id="k1",
                main_topic="k1-water",
                meter_type="water",
                n_digits=5,
                decimals=3,
                start_value=10.0,
                scenario="normal",
            ),
            FleetDeviceSpec(
                device_id="k2",
                main_topic="k2-elec",
                meter_type="electricity",
                n_digits=5,
                decimals=1,
                start_value=100.0,
                scenario="leak",
            ),
        ],
    )
    asyncio.run(
        run_fleet(
            cfg,
            max_ticks=3,
            publisher_factory=lambda *a, **k: rec,
            now_fn=lambda: "2026-06-27T10:00:00",
        )
    )
    # 2 devices x 3 ticks = 6 readings
    assert len(rec.readings) == 6
    assert {r[0] for r in rec.readings} == {"k1-water", "k2-elec"}
