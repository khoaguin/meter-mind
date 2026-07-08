import json

from pydantic import BaseModel, Field

_JSON_ORDER = ("value", "raw", "pre", "error", "rate", "timestamp")
_FLAT_ORDER = tuple(k for k in _JSON_ORDER if k != "pre")  # no `pre` — D6


class Reading(BaseModel):
    """One jomjol meter read: raw OCR through validated value, plus provenance.

    Mirrors the jomjol AI-on-the-edge MQTT payload. All fields are strings —
    jomjol publishes them as strings on the wire, so we preserve them verbatim
    rather than coercing to float and risking precision/format drift.
    """

    value: str = Field(
        description=(
            "Validated read: raw after plausibility checks (consistency vs pre, "
            "rate bounds). The number to trust."
        )
    )
    raw: str = Field(
        description=(
            "Uncorrected OCR result — what digit recognition saw, pre-validation. "
            "Equals value when checks changed nothing."
        )
    )
    pre: str = Field(
        description=(
            "Previous accepted value. Basis for rate and the sanity check that a "
            "meter can't run backwards or jump implausibly."
        )
    )
    error: str = Field(
        description=(
            "Status string: 'no error' when clean, else the rejection reason "
            "(e.g. 'negative rate', 'rate too high')."
        )
    )
    rate: str = Field(
        description=(
            "Consumption rate: change per time unit derived from value − pre. "
            "'0.000000' means no measured flow this interval."
        )
    )
    timestamp: str = Field(
        description="ISO-8601 time of the read (e.g. '2021-09-18T18:09:46')."
    )

    def json_fields(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in _JSON_ORDER}

    def flat_fields(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in _FLAT_ORDER}

    def json_payload(self) -> str:
        return json.dumps(self.json_fields(), separators=(",", ":"))


class Topics:
    """Plain builder — holds no meter data, so not a Pydantic model (D5).

    A Pydantic `.json` property would also collide with BaseModel.json().
    """

    def __init__(self, main_topic: str, group: str = "main") -> None:
        self.main_topic = main_topic
        self.group = group

    @property
    def json(self) -> str:
        return f"{self.main_topic}/{self.group}/json"

    def field(self, name: str) -> str:
        return f"{self.main_topic}/{self.group}/{name}"

    @property
    def confidence(self) -> str:
        return f"{self.main_topic}/{self.group}/confidence"

    @property
    def meter_type(self) -> str:
        return f"{self.main_topic}/MeterType"

    def status(self, name: str) -> str:
        return f"{self.main_topic}/{name}"
