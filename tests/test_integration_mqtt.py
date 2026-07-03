"""End-to-end: a real subscriber on a real broker receives the jomjol-native
contract exactly as a flashed ESP32-CAM would publish it — /json is the
byte-level drop-in seam, `pre` rides only inside /json (D6), and
confidence/MeterType arrive as additive topics (D1).
"""

import json
import time
from pathlib import Path

import pytest

JSON_KEY_ORDER = ["value", "raw", "pre", "error", "rate", "timestamp"]
FLAT_FIELDS = ["value", "raw", "error", "rate", "timestamp"]  # 5, no `pre` — D6


@pytest.mark.integration
def test_subscriber_receives_native_json(digits_dir: Path, model_path: Path) -> None:
    import paho.mqtt.client as mqtt

    from edgesim.contract import Topics
    from edgesim.device import DeviceConfig, VirtualDevice
    from edgesim.imagery import CropBank
    from edgesim.publisher import Publisher
    from edgesim.reader import DigitReader

    received: list[tuple[str, str]] = []

    def on_message(
        client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage
    ) -> None:
        received.append((message.topic, message.payload.decode()))

    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    sub.on_message = on_message
    sub.connect("localhost", 1883)
    sub.subscribe("kiosk1-water/#")
    sub.loop_start()
    time.sleep(0.3)

    cfg = DeviceConfig(
        device_id="kiosk1",
        main_topic="kiosk1-water",
        meter_type="water",
        n_digits=5,
        decimals=3,
        start_value=10.0,
    )
    dev = VirtualDevice(cfg, DigitReader(model_path), CropBank(digits_dir))
    res = dev.step(1.0, rolling=False, now="2026-06-27T10:00:00")

    pub = Publisher("localhost")
    pub.connect()
    pub.publish_reading(
        Topics("kiosk1-water"), res.reading, res.confidence, res.meter_type
    )
    time.sleep(0.5)
    sub.loop_stop()

    by_topic = dict(received)
    # /json: the drop-in seam — exact key set, order, and string-typed values
    assert "kiosk1-water/main/json" in by_topic
    body = json.loads(by_topic["kiosk1-water/main/json"])
    assert set(body) == {"value", "raw", "pre", "error", "rate", "timestamp"}
    assert list(body) == JSON_KEY_ORDER
    assert all(isinstance(v, str) for v in body.values())
    # Flat topics: jomjol emits 5 alongside /json
    for name in FLAT_FIELDS:
        assert f"kiosk1-water/main/{name}" in by_topic
        assert by_topic[f"kiosk1-water/main/{name}"] == body[name]
    # Additive extensions (D1): confidence + MeterType, optional for consumers
    assert by_topic["kiosk1-water/MeterType"] == "water"
    float(by_topic["kiosk1-water/main/confidence"])  # numeric string
    # D6: pre travels inside /json only — no flat pre topic over the wire
    assert "kiosk1-water/main/pre" not in by_topic
