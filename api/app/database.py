from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./tradingview.db"

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


STATE_DATABASE_URL = "sqlite:///./state.db"

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
