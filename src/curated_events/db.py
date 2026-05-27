"""Database connection and bootstrap helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import get_settings

_engines: dict[str, object] = {}
_sessionmakers: dict[str, sessionmaker] = {}


def get_engine(database_url: Optional[str] = None):
    settings = get_settings()
    db_url = database_url or settings.database_url
    if db_url not in _engines:
        _engines[db_url] = create_engine(db_url, future=True)
    return _engines[db_url]


def get_sessionmaker(database_url: Optional[str] = None):
    settings = get_settings()
    db_url = database_url or settings.database_url
    if db_url not in _sessionmakers:
        engine = get_engine(database_url=db_url)
        _sessionmakers[db_url] = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return _sessionmakers[db_url]


def init_db(database_url: Optional[str] = None) -> None:
    from .models import Base

    Session = get_sessionmaker(database_url=database_url)
    engine = Session.kw["bind"]
    Base.metadata.create_all(bind=engine)

    # Ensure mapping constraints are always visible.
    return None


@contextmanager
def session_scope(database_url: Optional[str] = None):
    Session = get_sessionmaker(database_url=database_url)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
