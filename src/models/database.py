"""SQLAlchemy ORM models and database engine / session management.

Provides a single ``get_db`` dependency for FastAPI route injection and
helper functions for table creation at startup.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from src.config import get_settings
from src.models.schemas import Platform, PublishStatus, ReviewStatus

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if "sqlite" in settings.database_url
    else {},
    echo=settings.app_env == "development",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class ProfileIntelligenceORM(Base):
    """Persisted result of a profile intelligence analysis run."""

    __tablename__ = "profile_intelligence"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(Enum(Platform), nullable=False)
    username = Column(String(255), nullable=False, index=True)
    full_name = Column(String(512))
    follower_count = Column(Integer, default=0)
    content_dna_summary = Column(Text)
    report_json = Column(Text, nullable=False)  # Full JSON blob
    created_at = Column(DateTime, default=datetime.utcnow)


class ContentCalendarORM(Base):
    """Persisted content calendar with revision history."""

    __tablename__ = "content_calendars"

    id = Column(Integer, primary_key=True, index=True)
    calendar_id = Column(String(36), unique=True, index=True, nullable=False)
    user_username = Column(String(255), nullable=False, index=True)
    period_days = Column(Integer, default=14)
    calendar_json = Column(Text, nullable=False)
    is_finalised = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    finalised_at = Column(DateTime, nullable=True)
    entries = relationship(
        "CalendarEntryORM", back_populates="calendar", cascade="all, delete-orphan"
    )


class CalendarEntryORM(Base):
    """Individual entry within a content calendar."""

    __tablename__ = "calendar_entries"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(String(36), unique=True, index=True, nullable=False)
    calendar_id = Column(
        String(36), ForeignKey("content_calendars.calendar_id"), nullable=False
    )
    day_number = Column(Integer, nullable=False)
    platform = Column(Enum(Platform), nullable=False)
    topic = Column(String(512), nullable=False)
    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    calendar = relationship("ContentCalendarORM", back_populates="entries")


class GeneratedPostORM(Base):
    """Persisted generated post content."""

    __tablename__ = "generated_posts"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(36), unique=True, index=True, nullable=False)
    calendar_entry_id = Column(String(36), nullable=False, index=True)
    platform = Column(Enum(Platform), nullable=False)
    body_copy = Column(Text)
    hashtags_json = Column(Text)  # JSON array
    visual_prompt = Column(Text)
    review_status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    revision_notes = Column(Text, default="")
    generated_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    publish_records = relationship(
        "PublishRecordORM", back_populates="post", cascade="all, delete-orphan"
    )


class PublishRecordORM(Base):
    """Publish outcome record for a generated post."""

    __tablename__ = "publish_records"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(String(36), unique=True, index=True, nullable=False)
    post_id = Column(String(36), ForeignKey("generated_posts.post_id"), nullable=False)
    platform = Column(Enum(Platform), nullable=False)
    publish_status = Column(Enum(PublishStatus), default=PublishStatus.QUEUED)
    platform_post_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    post = relationship("GeneratedPostORM", back_populates="publish_records")


class EngagementSnapshotORM(Base):
    """Engagement snapshot for post-publish impact tracking."""

    __tablename__ = "engagement_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(36), nullable=False, index=True)
    platform_post_id = Column(String(255))
    platform = Column(Enum(Platform), nullable=False)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    captured_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_tables() -> None:
    """Create all ORM tables in the configured database.

    Safe to call multiple times (uses ``CREATE TABLE IF NOT EXISTS``).
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session.

    Yields:
        An active database session, automatically closed on exit.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
