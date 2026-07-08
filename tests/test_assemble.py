from edgesim.assemble import assemble
from edgesim.reader import DigitPrediction


def _p(cls: int, conf: float) -> DigitPrediction:
    return DigitPrediction(class_index=cls, confidence=conf)


def test_clean_value_with_decimals():
    preds = [
        _p(1, 0.99),
        _p(0, 0.99),
        _p(1, 0.98),
        _p(7, 0.97),
        _p(0, 0.99),
        _p(1, 0.96),
        _p(5, 0.95),
        _p(4, 0.99),
    ]
    r = assemble(preds, decimals=3, pre_value="10170.000")
    assert r.value == "10170.154"
    assert r.error == "no error"
    assert r.has_nan is False
    assert abs(r.confidence - 0.95) < 1e-6


def test_nan_holds_previous_value():
    preds = [_p(1, 0.99), _p(10, 0.40), _p(1, 0.98)]  # middle digit NaN
    r = assemble(preds, decimals=0, pre_value="909")
    assert r.has_nan is True
    assert r.error == "digit position 1 uncertain"
    assert r.value == "909"  # held at pre
    assert r.confidence == 0.40
