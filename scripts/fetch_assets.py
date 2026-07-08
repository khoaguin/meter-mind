"""Download jomjol's float digit model + a sample of labeled digit crops.

Model: from AI-on-the-edge-device/sd-card/config (raw GitHub).
Crops: shallow-clone neural-network-digital-counter-readout, read the FLAT
`<label>-<n>.jpg` files, and bucket a subset per class (0-9 and NaN) into
data/digits/<label>/ for reader validation + meter compositing.
"""

import re
import shutil
import subprocess
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "data" / "models"
DIGITS = ROOT / "data" / "digits"
MODEL_URL = (
    "https://raw.githubusercontent.com/jomjol/AI-on-the-edge-device/"
    "main/sd-card/config/dig-class11_1701_s2.tflite"
)
DATASET_REPO = "https://github.com/jomjol/neural-network-digital-counter-readout.git"
# FLAT folder of <label>-<n>.jpg crops (verified layout):
DATASET_SUBDIR = "03_data_resize_all-use_for_training"
PER_CLASS = 40  # enough to validate + composite
# Leading label token. Verified conventions in the current dataset (2026-07):
#   "0-1.jpg", "0 - 0_1_<ts>.jpg", "2 -10_5_<ts>.jpg", "1.0_<hash>.jpg",
#   "NaN_0_ROI4_<ts>.jpg". Historic jomjol encoding used "10" for NaN.
# Label = leading "NaN" (any case) or 1-2 digits, optional ".<d>" decimal part,
# followed by a separator (space/./_/-) or end of stem.
_LABEL_RE = re.compile(r"^(nan|\d{1,2})(?:\.\d+)?(?=[ ._-]|$)", re.IGNORECASE)
_NAN_PREFIXES = {"10", "nan"}


def fetch_model() -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    dst = MODELS / "dig-class11_1701_s2.tflite"
    if dst.exists():
        print(f"model exists: {dst}")
        return
    print(f"downloading model -> {dst}")
    urllib.request.urlretrieve(MODEL_URL, dst)


def _label_of(path: Path) -> str | None:
    """'7-3.jpg' -> '7'; '1.0_x.jpg' -> '1'; 'NaN_x.jpg'/'10-5.jpg' -> 'NaN'.

    Returns None if unrecognised.
    """
    m = _LABEL_RE.match(path.stem)
    if m is None:
        return None
    prefix = m.group(1)
    if prefix.lower() in _NAN_PREFIXES:
        return "NaN"
    if prefix.isdigit() and 0 <= int(prefix) <= 9:
        return prefix
    return None


def fetch_crops() -> None:
    if DIGITS.exists() and any(DIGITS.iterdir()):
        print(f"crops exist: {DIGITS}")
        return
    DIGITS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        print("shallow-cloning dataset (may take a minute)...")
        subprocess.run(["git", "clone", "--depth", "1", DATASET_REPO, tmp], check=True)
        src_root = Path(tmp) / DATASET_SUBDIR
        if not src_root.exists():
            raise SystemExit(
                f"expected {DATASET_SUBDIR} in dataset repo; "
                f"inspect {tmp} and update DATASET_SUBDIR"
            )
        buckets: dict[str, list[Path]] = defaultdict(list)
        for p in sorted(src_root.rglob("*")):
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
                continue
            label = _label_of(p)
            if label is not None:
                buckets[label].append(p)
        if not buckets:
            raise SystemExit(
                f"no labelled crops parsed from {src_root}; "
                "inspect filenames and update _label_of()"
            )
        for label, paths in sorted(buckets.items()):
            out = DIGITS / label
            out.mkdir(parents=True, exist_ok=True)
            for img in paths[:PER_CLASS]:
                shutil.copy(img, out / img.name)
            print(f"  {label}: {min(len(paths), PER_CLASS)} crops")


if __name__ == "__main__":
    fetch_model()
    fetch_crops()
    print("done.")
