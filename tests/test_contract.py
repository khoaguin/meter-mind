import json

from edgesim.contract import Reading, Topics


def _reading() -> Reading:
    return Reading(
        value="10170.154",
        raw="10170.154",
        pre="10170.000",
        error="no error",
        rate="0.000000",
        timestamp="2021-09-18T18:09:46",
    )


def test_json_payload_is_jomjol_native():
    payload = _reading().json_payload()
    assert json.loads(payload) == {
        "value": "10170.154",
        "raw": "10170.154",
        "pre": "10170.000",
        "error": "no error",
        "rate": "0.000000",
        "timestamp": "2021-09-18T18:09:46",
    }
    # exact key order
    assert list(json.loads(payload).keys()) == [
        "value",
        "raw",
        "pre",
        "error",
        "rate",
        "timestamp",
    ]


def test_flat_fields_exclude_pre():
    # Bugfix B / D6: jomjol emits no flat `pre` topic — only `/json` carries pre.
    assert set(_reading().flat_fields()) == {
        "value",
        "raw",
        "error",
        "rate",
        "timestamp",
    }
    assert "pre" not in _reading().flat_fields()


def test_topics():
    t = Topics(main_topic="kiosk1-water")
    assert t.json == "kiosk1-water/main/json"
    assert t.field("value") == "kiosk1-water/main/value"
    assert t.confidence == "kiosk1-water/main/confidence"
    assert t.meter_type == "kiosk1-water/MeterType"
    assert t.status("Hostname") == "kiosk1-water/Hostname"
