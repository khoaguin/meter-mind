from pathlib import Path
from typing import Any, cast

import numpy as np
from PIL import Image
from pydantic import BaseModel

_W, _H = 20, 32  # model input width, height


class DigitPrediction(BaseModel):
    class_index: int  # 0..9 digit, 10 == NaN
    confidence: float  # softmax max, 0..1


def _load_interpreter(model_path: str) -> Any:
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:  # fallback runtime
        from tensorflow.lite import Interpreter  # type: ignore[import-not-found]
    itp = Interpreter(model_path=model_path)
    itp.allocate_tensors()
    return itp


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


class DigitReader:
    def __init__(self, model_path: str | Path) -> None:
        self._itp = _load_interpreter(str(model_path))
        self._in = cast(dict[str, Any], self._itp.get_input_details()[0])
        self._out = cast(dict[str, Any], self._itp.get_output_details()[0])
        self._dtype = self._in["dtype"]
        self._quant = self._in.get("quantization", (0.0, 0))

    def _prep(self, img: Image.Image) -> np.ndarray:
        arr = np.asarray(img.convert("RGB").resize((_W, _H)), dtype=np.float32)
        if np.issubdtype(self._dtype, np.floating):
            # float model trained on 0-255 RGB (no /255 rescale — jomjol CTfLiteClass.cpp)
            return arr.astype(np.float32)[None, ...]
        scale, zero = self._quant
        q = arr if scale == 0 else np.round(arr / scale) + zero
        return q.astype(self._dtype)[None, ...]

    def predict_crop(self, img: Image.Image) -> DigitPrediction:
        x = self._prep(img)
        self._itp.set_tensor(self._in["index"], x)
        self._itp.invoke()
        raw = self._itp.get_tensor(self._out["index"])[0].astype(np.float32)
        oscale, ozero = self._out.get("quantization", (0.0, 0))
        if not np.issubdtype(self._out["dtype"], np.floating) and oscale:
            raw = (raw - ozero) * oscale
        probs = _softmax(raw)
        idx = int(np.argmax(probs))
        return DigitPrediction(class_index=idx, confidence=float(probs[idx]))
