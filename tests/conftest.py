from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def model_path() -> Path:
    p = ROOT / "data" / "models" / "dig-class11_1701_s2.tflite"
    if not p.exists():
        pytest.skip("run scripts/fetch_assets.py first")
    return p


@pytest.fixture(scope="session")
def digits_dir() -> Path:
    p = ROOT / "data" / "digits"
    if not p.exists() or not any(p.iterdir()):
        pytest.skip("run scripts/fetch_assets.py first")
    return p
