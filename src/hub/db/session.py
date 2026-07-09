"""Engine + session for the one-file hub SQLite DB.

The DB location is env-overridable (`HUB_DB_PATH`, default `data/hub.db`) so
tests can redirect to a `tmp_path`. `init_db(engine)` takes any engine (the test
seam); `get_session()` stays parameter-free so it is reusable verbatim as the
FastAPI dependency in the REST phase.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

DB_PATH: Path = Path(os.environ.get("HUB_DB_PATH", "data/hub.db"))  # env-overridable
DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # data/ created if missing
engine: Engine = create_engine(f"sqlite:///{DB_PATH}")


def init_db(engine: Engine = engine) -> None:
    SQLModel.metadata.create_all(
        engine
    )  # no Alembic — one file; engine param = test seam


def get_session() -> Iterator[
    Session
]:  # generator; verbatim FastAPI dep in the REST phase
    with Session(engine) as session:
        yield session
