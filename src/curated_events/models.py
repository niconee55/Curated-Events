"""ORM models used by the discovery and calendar sync pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    events: Mapped[List["Event"]] = relationship("Event", back_populates="source")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    internal_event_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[str | None] = mapped_column(String(150))
    start_dt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_dt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venue_name: Mapped[str | None] = mapped_column(String(200))
    venue_city: Mapped[str | None] = mapped_column(String(100))
    venue_country: Mapped[str | None] = mapped_column(String(100))
    price_min: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    ticket_url: Mapped[str | None] = mapped_column(String(500))
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reminder: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))

    source: Mapped[Source | None] = relationship("Source", back_populates="events")
    calendar_mappings: Mapped[List["CalendarMapping"]] = relationship("CalendarMapping", back_populates="event")


class CalendarMapping(Base):
    __tablename__ = "calendar_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    internal_event_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    google_event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="synced", nullable=False)

    event: Mapped[Event] = relationship("Event", back_populates="calendar_mappings")

    __table_args__ = (
        UniqueConstraint("internal_event_id", name="uq_calendar_mappings_internal_event_id"),
        UniqueConstraint("event_id", name="uq_calendar_mappings_event_id"),
    )


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    run_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    candidates: Mapped[int] = mapped_column(default=0, nullable=False)
    kept: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(default=0, nullable=False)
    synced: Mapped[int] = mapped_column(default=0, nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
