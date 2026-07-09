from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from hub.core import narrate
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
def db_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    """A tmp SQLite engine bound to the module factory so DB-backed service fns read it.

    Phase 2's `service` fns open `Session(hub.db.session.engine)` internally; patching
    that module attribute redirects them to this tmp DB — the real data/hub.db is never
    touched, and the patch auto-reverts after the test.
    """
    from hub.db import session as db_session

    engine = create_engine(f"sqlite:///{tmp_path}/hub.db")
    monkeypatch.setattr(db_session, "engine", engine)
    init_db(engine)
    return engine


@pytest.fixture
def seeded_session(db_engine: Engine) -> Iterator[Session]:
    """A session over a tmp engine already loaded from the frozen seed.yaml."""
    with Session(db_engine) as session:
        load_seed(session)
        yield session


@pytest.fixture(autouse=True)
def _mock_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests offline + deterministic — no live Claude call (the one live call
    is exercised manually at rehearsal). Tests that assert the fallback path re-patch this."""
    monkeypatch.setattr(
        narrate,
        "explain_anomaly_en",
        lambda device_id,
        kind,
        detected_at,
        factor: f"[stub] {kind} {factor}x {detected_at}",
    )
