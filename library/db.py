"""SQLAlchemy models and session management for the asset library."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


class Character(Base):
    __tablename__ = "characters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(String, default="")
    height_cm: Mapped[float] = mapped_column(Float, default=170.0)
    sheet_path: Mapped[str] = mapped_column(String, default="")
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Outfit(Base):
    __tablename__ = "outfits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(String, default="")
    ref_image_path: Mapped[str] = mapped_column(String, default="")
    tags: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Scene(Base):
    __tablename__ = "scenes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(String, default="")
    image_path: Mapped[str] = mapped_column(String, default="")
    depth_map_path: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Panel(Base):
    __tablename__ = "panels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    image_path: Mapped[str] = mapped_column(String, default="")
    compose_json: Mapped[str] = mapped_column(String, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


@lru_cache(maxsize=1)
def _engine():
    settings = get_settings()
    db_path: Path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@lru_cache(maxsize=1)
def _session_factory():
    return sessionmaker(bind=_engine(), autoflush=False, expire_on_commit=False)


def session() -> Session:
    """Return a new SQLAlchemy session. Callers should close it or use a
    context manager."""
    return _session_factory()()


def reset_caches_for_tests() -> None:
    _engine.cache_clear()
    _session_factory.cache_clear()
