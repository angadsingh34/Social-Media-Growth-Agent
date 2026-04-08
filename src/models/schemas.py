"""Pydantic v2 request/response schemas for all API endpoints and inter-agent DTOs.

These schemas serve as the single source of truth for data shapes across the
REST API layer, the orchestrator, and each agent.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    """Supported social media platforms."""

    LINKEDIN = "linkedin"
    TWITTER = "twitter"


class ContentFormat(str, Enum):
    """Content format taxonomy used across agents."""

    SHORT_POST = "short_post"
    THREAD = "thread"
    ARTICLE = "article"
    LISTICLE = "listicle"
    POLL = "poll"
    CAROUSEL = "carousel"


class ReviewStatus(str, Enum):
    """Review lifecycle status for a piece of generated content."""

    PENDING = "pending"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"


class PublishStatus(str, Enum):
    """Publishing lifecycle status."""

    QUEUED = "queued"
    POSTED = "posted"
    FAILED = "failed"
    CLIPBOARD = "clipboard"  # manual copy fallback


class PipelineStage(str, Enum):
    """High-level pipeline stage for orchestrator state tracking."""

    PROFILE_ANALYSIS = "profile_analysis"
    COMPETITIVE_ANALYSIS = "competitive_analysis"
    CALENDAR_GENERATION = "calendar_generation"
    CALENDAR_REVIEW = "calendar_review"
    CONTENT_GENERATION = "content_generation"
    CONTENT_REVIEW = "content_review"
    PUBLISHING = "publishing"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# Profile Intelligence
# ---------------------------------------------------------------------------


class WritingStyleProfile(BaseModel):
    """Distilled writing style characteristics of a profile."""

    model_config = ConfigDict(from_attributes=True)

    tone: str = Field(description="e.g. 'authoritative', 'casual', 'motivational'")
    vocabulary_level: str = Field(description="e.g. 'technical', 'accessible', 'mixed'")
    avg_post_length: int = Field(description="Average post length in words")
    uses_emojis: bool = False
    uses_hashtags: bool = True
    signature_phrases: list[str] = Field(default_factory=list)


class ProfileIntelligenceReport(BaseModel):
    """Full output of the Profile Intelligence Agent (FR-1)."""

    model_config = ConfigDict(from_attributes=True)

    platform: Platform
    username: str
    full_name: str
    follower_count: int = 0
    writing_style: WritingStyleProfile
    top_topics: list[str] = Field(default_factory=list)
    content_formats: list[ContentFormat] = Field(default_factory=list)
    posting_cadence_per_week: float = 0.0
    high_engagement_topics: list[str] = Field(default_factory=list)
    high_engagement_formats: list[ContentFormat] = Field(default_factory=list)
    content_dna_summary: str = Field(description="2-3 sentence narrative summary")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Competitive Analysis
# ---------------------------------------------------------------------------


class ContentGap(BaseModel):
    """A topic or format that the user under-covers vs competitors."""

    topic_or_format: str
    competitor_name: str
    engagement_signal: str
    recommendation: str


class CompetitiveAnalysisReport(BaseModel):
    """Output of the Competitive Landscape Agent (FR-2)."""

    model_config = ConfigDict(from_attributes=True)

    user_username: str
    analysed_competitors: list[str] = Field(default_factory=list)
    content_gaps: list[ContentGap] = Field(default_factory=list)
    trending_topics_in_niche: list[str] = Field(default_factory=list)
    high_engagement_formats_in_niche: list[ContentFormat] = Field(default_factory=list)
    strategic_opportunities: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Content Calendar
# ---------------------------------------------------------------------------


class CalendarEntry(BaseModel):
    """A single scheduled post entry in the content calendar."""

    model_config = ConfigDict(from_attributes=True)

    entry_id: str
    day_number: int
    platform: Platform
    topic: str
    content_format: ContentFormat
    scheduled_time: str = Field(description="e.g. '09:00 AM'")
    rationale: str = Field(description="Why this topic/format was chosen")
    status: ReviewStatus = ReviewStatus.PENDING


class ContentCalendar(BaseModel):
    """The full content calendar (FR-3 output)."""

    model_config = ConfigDict(from_attributes=True)

    calendar_id: str
    user_username: str
    period_days: int
    entries: list[CalendarEntry] = Field(default_factory=list)
    is_finalised: bool = False
    revision_history: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalised_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Content Generation
# ---------------------------------------------------------------------------


class GeneratedPost(BaseModel):
    """Full generated content for a single calendar entry (FR-4)."""

    model_config = ConfigDict(from_attributes=True)

    post_id: str
    calendar_entry_id: str
    platform: Platform
    body_copy: str
    hashtags: list[str] = Field(default_factory=list)
    visual_prompt: str = Field(description="Detailed image-generation prompt")
    review_status: ReviewStatus = ReviewStatus.PENDING
    revision_notes: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


class PublishRecord(BaseModel):
    """Tracks the publish outcome of a post."""

    model_config = ConfigDict(from_attributes=True)

    record_id: str
    post_id: str
    platform: Platform
    publish_status: PublishStatus = PublishStatus.QUEUED
    platform_post_id: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Impact Tracker
# ---------------------------------------------------------------------------


class PostEngagementSnapshot(BaseModel):
    """A point-in-time engagement snapshot for a published post."""

    post_id: str
    platform_post_id: str
    platform: Platform
    likes: int = 0
    comments: int = 0
    shares: int = 0
    impressions: int = 0
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class AdaptiveSuggestion(BaseModel):
    """A recommended calendar adjustment based on post performance."""

    based_on_post_id: str
    observation: str
    suggested_action: str
    affected_entry_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API Request / Response wrappers
# ---------------------------------------------------------------------------


class ProfileAnalysisRequest(BaseModel):
    """Request body for the profile analysis endpoint."""

    platform: Platform
    username: str
    use_mock: bool = True


class CalendarGenerationRequest(BaseModel):
    """Request body for calendar generation."""

    user_username: str
    period_days: int = Field(default=14, ge=1, le=90)
    platforms: list[Platform] = Field(
        default_factory=lambda: [Platform.LINKEDIN, Platform.TWITTER]
    )
    preferences: Optional[dict[str, Any]] = None


class CalendarFeedbackRequest(BaseModel):
    """User feedback for an HITL calendar review round."""

    calendar_id: str
    feedback: str
    approve: bool = False


class ContentRegenerationRequest(BaseModel):
    """Request to regenerate a specific component of a post."""

    post_id: str
    component: str = Field(description="'body_copy' | 'hashtags' | 'visual_prompt'")
    instructions: Optional[str] = None


class PublishRequest(BaseModel):
    """Request to publish approved posts."""

    post_ids: list[str]
    platforms: list[Platform]


class HealthResponse(BaseModel):
    """Standard health-check response."""

    status: str = "ok"
    version: str = "1.0.0"
    environment: str
    services: dict[str, str] = Field(default_factory=dict)
