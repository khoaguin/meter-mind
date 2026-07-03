from collections.abc import Callable
from typing import Protocol

from edgesim.contract import Reading, Topics


class MqttClientLike(Protocol):
    """Subset of the paho-mqtt Client surface the publisher uses."""

    def connect(self, host: str, port: int) -> object: ...

    def loop_start(self) -> object: ...

    def publish(self, topic: str, payload: str) -> object: ...


def _default_client_factory() -> MqttClientLike:
    import paho.mqtt.client as mqtt

    # paho-mqtt 2.x requires an explicit callback API version.
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


class Publisher:
    def __init__(
        self,
        host: str,
        port: int = 1883,
        client_factory: Callable[[], MqttClientLike] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._client = (client_factory or _default_client_factory)()

    def connect(self) -> None:
        self._client.connect(self._host, self._port)
        self._client.loop_start()

    def publish_reading(
        self, topics: Topics, reading: Reading, confidence: float, meter_type: str
    ) -> list[tuple[str, str]]:
        sent: list[tuple[str, str]] = []
        # flat_fields() is the 5-field set (no `pre`) — D6
        for name, val in reading.flat_fields().items():
            sent.append((topics.field(name), val))
        sent.append((topics.json, reading.json_payload()))  # /json carries all 6
        sent.append((topics.confidence, f"{confidence:.4f}"))
        sent.append((topics.meter_type, meter_type))
        for topic, payload in sent:
            self._client.publish(topic, payload)
        return sent

    def publish_status(
        self,
        topics: Topics,
        hostname: str,
        ip: str,
        mac: str,
        uptime: int,
        rssi: int,
    ) -> None:
        for name, val in (
            ("Hostname", hostname),
            ("IP", ip),
            ("MAC", mac),
            ("Uptime", str(uptime)),
            ("wifiRSSI", str(rssi)),
        ):
            self._client.publish(topics.status(name), val)
