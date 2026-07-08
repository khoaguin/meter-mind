from pydantic import BaseModel

from edgesim.reader import DigitPrediction


class MeterReadResult(BaseModel):
    value: str
    error: str
    confidence: float
    has_nan: bool


def _with_decimals(digits: str, decimals: int) -> str:
    if decimals <= 0:
        return digits
    whole, frac = digits[:-decimals], digits[-decimals:]
    return f"{whole or '0'}.{frac}"


def assemble(
    predictions: list[DigitPrediction], decimals: int, pre_value: str
) -> MeterReadResult:
    confidence = min((p.confidence for p in predictions), default=1.0)
    first_nan = next(
        (i for i, p in enumerate(predictions) if p.class_index == 10), None
    )
    if first_nan is not None:
        return MeterReadResult(
            value=pre_value,
            error=f"digit position {first_nan} uncertain",
            confidence=confidence,
            has_nan=True,
        )
    digits = "".join(str(p.class_index) for p in predictions)
    return MeterReadResult(
        value=_with_decimals(digits, decimals),
        error="no error",
        confidence=confidence,
        has_nan=False,
    )
