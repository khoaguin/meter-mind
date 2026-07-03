from pathlib import Path
from typing import Any, cast


def _interpreter(model_path: Path):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        from tensorflow.lite import Interpreter  # type: ignore

    itp = Interpreter(model_path=str(model_path))
    itp.allocate_tensors()
    return itp


def test_model_shape_and_classes(model_path: Path) -> None:
    itp = _interpreter(model_path)
    inp = cast(dict[str, Any], itp.get_input_details()[0])
    out = cast(dict[str, Any], itp.get_output_details()[0])
    # NHWC: [1, 32, 20, 3]  (H=32, W=20, RGB) — source of truth for the shape claim
    assert list(inp["shape"]) == [1, 32, 20, 3], inp["shape"]
    assert out["shape"][-1] == 11, out["shape"]
