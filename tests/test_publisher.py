from edgesim.contract import Reading, Topics
from edgesim.publisher import Publisher


class FakeClient:
    def __init__(self):
        self.published = []
        self.connected = False

    def connect(self, host, port):  # paho signature subset
        self.connected = True

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        self.connected = False

    def publish(self, topic, payload):
        self.published.append((topic, payload))


def _reading() -> Reading:
    return Reading(
        value="11.234",
        raw="11.234",
        pre="10.000",
        error="no error",
        rate="1.234000",
        timestamp="2026-06-27T10:00:00",
    )


def test_publish_reading_emits_full_contract():
    fake = FakeClient()
    pub = Publisher("localhost", client_factory=lambda: fake)
    pub.connect()
    topics = Topics(main_topic="kiosk1-water")
    sent = pub.publish_reading(topics, _reading(), confidence=0.97, meter_type="water")
    topic_set = {t for t, _ in sent}
    assert "kiosk1-water/main/value" in topic_set
    assert "kiosk1-water/main/json" in topic_set
    assert "kiosk1-water/main/confidence" in topic_set
    assert "kiosk1-water/MeterType" in topic_set
    # Bugfix B / D6: pre is NOT a flat topic (only inside /json)
    assert "kiosk1-water/main/pre" not in topic_set
    # /json payload is the native body (all 6 keys, incl. pre)
    json_payload = dict(sent)["kiosk1-water/main/json"]
    assert json_payload == _reading().json_payload()
    assert '"pre"' in json_payload
    # confidence formatted to 4 dp
    assert dict(sent)["kiosk1-water/main/confidence"] == "0.9700"
