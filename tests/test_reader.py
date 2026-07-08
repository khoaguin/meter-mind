from pathlib import Path
from typing import Any, cast

from PIL import Image


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


def test_reader_accuracy_on_real_crops(model_path: Path, digits_dir: Path) -> None:
    from edgesim.reader import DigitReader

    reader = DigitReader(model_path)
    label_map = {str(d): d for d in range(10)}
    label_map["NaN"] = 10

    total = correct = 0
    for cls_name, expected in label_map.items():
        cls_dir = digits_dir / cls_name
        if not cls_dir.exists():
            continue
        for img_path in sorted(cls_dir.glob("*"))[:20]:
            with Image.open(img_path) as im:
                pred = reader.predict_crop(im.convert("RGB"))
            total += 1
            correct += int(pred.class_index == expected)
            assert 0.0 <= pred.confidence <= 1.0
    assert total > 0
    acc = correct / total
    assert acc >= 0.85, f"accuracy {acc:.2f} too low — check normalization/H-W"
