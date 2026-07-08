from edgesim.device import DeviceConfig, VirtualDevice
from edgesim.imagery import CropBank
from edgesim.reader import DigitReader


def _device(digits_dir, model_path):
    cfg = DeviceConfig(
        device_id="kiosk1",
        main_topic="kiosk1-water",
        meter_type="water",
        n_digits=5,
        decimals=3,
        start_value=10.000,
    )
    return VirtualDevice(cfg, DigitReader(model_path), CropBank(digits_dir, seed=5))


def test_step_produces_jomjol_reading(digits_dir, model_path):
    dev = _device(digits_dir, model_path)
    res = dev.step(delta=1.234, rolling=False, now="2026-06-27T10:00:00")
    assert res.reading.error == "no error"
    assert res.reading.timestamp == "2026-06-27T10:00:00"
    assert res.meter_type == "water"
    assert 0.0 <= res.confidence <= 1.0
    # rate = new - pre = 1.234 (value advanced from 10.000 to 11.234)
    assert float(res.reading.rate) > 1.0


def test_rolling_step_flags_error(digits_dir, model_path):
    dev = _device(digits_dir, model_path)
    res = dev.step(delta=0.5, rolling=True, now="2026-06-27T10:00:05")
    assert res.reading.error != "no error"
