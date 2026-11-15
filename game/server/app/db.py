"""Database engine and session helpers (SQLAlchemy 2.x, SQLite by default)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)

if DB_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(conn, _record):  # pragma: no cover - trivial
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Tiny migration: add columns introduced after a database was created (SQLite ALTER TABLE ADD COLUMN)."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl_type = col.type.compile(engine.dialect)
                default = ""
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    v = col.default.arg
                    default = f" DEFAULT {int(v) if isinstance(v, bool) else repr(v) if isinstance(v, str) else v}"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{default}'))


@contextmanager
def session_scope() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
