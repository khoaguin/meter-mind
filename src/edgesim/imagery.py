from pathlib import Path

from PIL import Image

_W, _H = 20, 32
_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


class CropBank:
    def __init__(self, digits_dir: str | Path, seed: int = 0) -> None:
        root = Path(digits_dir)
        self._by_label: dict[str, list[Path]] = {}
        for label in [*(str(d) for d in range(10)), "NaN"]:
            d = root / label
            if d.exists():
                self._by_label[label] = sorted(
                    p for p in d.iterdir() if p.suffix.lower() in _EXTS
                )
        self._counter = seed

    def pick(self, label: str) -> Image.Image:
        paths = self._by_label.get(label)
        if not paths:
            raise KeyError(f"no crops for label {label!r}")
        self._counter += 1
        path = paths[self._counter % len(paths)]
        return Image.open(path).convert("RGB").resize((_W, _H))


def render_strip(
    value_digits: str, bank: CropBank, rolling_index: int | None = None
) -> Image.Image:
    strip = Image.new("RGB", (_W * len(value_digits), _H))
    for i, ch in enumerate(value_digits):
        label = "NaN" if i == rolling_index else ch
        strip.paste(bank.pick(label), (i * _W, 0))
    return strip


def split_strip(strip: Image.Image, n: int) -> list[Image.Image]:
    return [strip.crop((i * _W, 0, (i + 1) * _W, _H)) for i in range(n)]
