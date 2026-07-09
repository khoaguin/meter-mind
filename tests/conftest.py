from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from hub.db.seed_loader import load_seed
from hub.db.session import init_db

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


@pytest.fixture
def db_engine(tmp_path: Path) -> Engine:
    """A throwaway SQLite engine at tmp_path — seeding never touches the real data/hub.db."""
    engine = create_engine(f"sqlite:///{tmp_path}/hub.db")
    init_db(engine)
    return engine


@pytest.fixture
def seeded_session(db_engine: Engine) -> Iterator[Session]:
    """A session over a tmp engine already loaded from the frozen seed.yaml."""
    with Session(db_engine) as session:
        load_seed(session)
        yield session
