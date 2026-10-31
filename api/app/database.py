from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_DIR = Path(__file__).resolve().parents[1] / "db"

DATABASE_URL = f"sqlite:///{DB_DIR / 'stock.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


STATE_DATABASE_URL = f"sqlite:///{DB_DIR / 'state.db'}"

state_engine = create_engine(STATE_DATABASE_URL, connect_args={"check_same_thread": False})
StateSessionLocal = sessionmaker(bind=state_engine, autoflush=False, autocommit=False)


class StateBase(DeclarativeBase):
    pass


def get_state_db() -> Generator[Session, None, None]:
    db = StateSessionLocal()
    try:
        yield db
    finally:
        db.close()
