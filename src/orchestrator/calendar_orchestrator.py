"""Content Calendar Orchestrator with HITL support (FR-3).

Synthesises profile and competitive intelligence to generate a grounded
14-day (or custom-period) content calendar. Supports conversational revision
rounds while preserving full edit history.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from src.models.schemas import (
    CalendarEntry,
    CompetitiveAnalysisReport,
    ContentCalendar,
    ContentFormat,
    Platform,
    ProfileIntelligenceReport,
)
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService
from src.utils.helpers import safe_json_parse
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_CALENDAR_SYSTEM = """You are an expert content strategist. Generate a data-driven content
calendar grounded in the provided profile and competitive intelligence.
Return ONLY valid JSON — no markdown, no commentary."""

_CALENDAR_TEMPLATE = """Generate a {period_days}-day content calendar for {username}.

Profile Intelligence Summary:
{profile_summary}

Competitive Intelligence Summary:
{competitive_summary}

Calendar Rules:
- Distribute content across LinkedIn and Twitter/X
- Vary content formats (short_post, thread, article, listicle, poll, carousel)
- Ground every topic in the profile analysis or competitive gaps — no arbitrary topics
- Aim for 1-2 posts per day
- Schedule around peak engagement times (9am, 12pm, 6pm)

Return JSON:
{{
  "entries": [
    {{
      "entry_id": "<unique uuid>",
      "day_number": <integer 1-{period_days}>,
      "platform": "linkedin" or "twitter",
      "topic": "<specific topic string>",
      "content_format": "<short_post|thread|article|listicle|poll|carousel>",
      "scheduled_time": "<HH:MM AM/PM>",
      "rationale": "<one sentence grounding this entry in the analysis>"
    }}
  ]
}}"""

_REVISION_SYSTEM = """You are a content calendar manager. Apply the user's feedback to
revise the calendar. Return ONLY the complete revised calendar JSON."""

_REVISION_TEMPLATE = """Here is the current content calendar:
{calendar_json}

User feedback:
{feedback}

Apply the feedback precisely. If the user asks to replace, move, or modify entries,
do so while maintaining overall strategy coherence. Return the full revised JSON
in the same format as the input."""


class CalendarOrchestrator:
    """Generates and iteratively revises content calendars via HITL.

    Attributes:
        llm: LLM service for calendar generation and revision.
        retriever: RAG retriever for grounded generation.
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the CalendarOrchestrator.

        Args:
            llm: Shared LLM service instance.
            retriever: Shared RAG retriever instance.
        """
        self.llm = llm or LLMService()
        self.retriever = retriever or RAGRetriever()

    def generate(
        self,
        username: str,
        period_days: int,
        profile_report: ProfileIntelligenceReport,
        competitive_report: CompetitiveAnalysisReport,
        preferences: Optional[dict[str, Any]] = None,
    ) -> ContentCalendar:
        """Generate an initial content calendar grounded in analysis reports.

        Args:
            username: The user's social media handle.
            period_days: Number of days to cover (e.g. 14).
            profile_report: User's profile intelligence report.
            competitive_report: Competitive landscape analysis report.
            preferences: Optional user preferences (e.g. preferred topics).

        Returns:
            A validated ContentCalendar instance.
        """
        logger.info("calendar_generate_start", username=username, days=period_days)

        # Build concise summaries for the prompt
        profile_summary = (
            f"Topics: {', '.join(profile_report.top_topics[:6])}\n"
            f"Style: {profile_report.writing_style.tone}, "
            f"{profile_report.writing_style.vocabulary_level} vocabulary\n"
            f"Best formats: {', '.join(f.value for f in profile_report.high_engagement_formats[:3])}\n"
            f"DNA: {profile_report.content_dna_summary}"
        )

        competitive_summary = (
            f"Trending topics: {', '.join(competitive_report.trending_topics_in_niche[:5])}\n"
            f"Opportunities: {'; '.join(competitive_report.strategic_opportunities[:3])}\n"
            f"Gaps: {'; '.join(g.topic_or_format for g in competitive_report.content_gaps[:3])}"
        )

        prompt = _CALENDAR_TEMPLATE.format(
            period_days=period_days,
            username=username,
            profile_summary=profile_summary,
            competitive_summary=competitive_summary,
        )

        raw = self.llm.complete(user_prompt=prompt, system_prompt=_CALENDAR_SYSTEM)
        parsed = safe_json_parse(raw)

        entries = self._parse_entries(parsed)
        calendar = ContentCalendar(
            calendar_id=str(uuid.uuid4()),
            user_username=username,
            period_days=period_days,
            entries=entries,
        )

        logger.info(
            "calendar_generated",
            username=username,
            entry_count=len(entries),
            calendar_id=calendar.calendar_id,
        )
        return calendar

    def revise(self, calendar: ContentCalendar, feedback: str) -> ContentCalendar:
        """Apply user HITL feedback to produce a revised calendar.

        Args:
            calendar: The current content calendar.
            feedback: Free-text user feedback (e.g. 'Move Day 3 thread to Friday').

        Returns:
            A revised ContentCalendar with the feedback applied and logged.
        """
        logger.info(
            "calendar_revise_start",
            calendar_id=calendar.calendar_id,
            feedback_preview=feedback[:80],
        )

        calendar_json = json.dumps(
            [e.model_dump() for e in calendar.entries], indent=2, default=str
        )
        prompt = _REVISION_TEMPLATE.format(
            calendar_json=calendar_json, feedback=feedback
        )
        raw = self.llm.complete(user_prompt=prompt, system_prompt=_REVISION_SYSTEM)

        parsed = safe_json_parse(raw)
        if isinstance(parsed, dict) and "entries" in parsed:
            revised_entries = self._parse_entries(parsed)
        elif isinstance(parsed, list):
            revised_entries = self._parse_entries({"entries": parsed})
        else:
            logger.warning("calendar_revision_parse_failed_keeping_original")
            revised_entries = calendar.entries

        calendar.entries = revised_entries
        calendar.revision_history.append(feedback)

        logger.info(
            "calendar_revised",
            calendar_id=calendar.calendar_id,
            revision_round=len(calendar.revision_history),
        )
        return calendar

    def finalise(self, calendar: ContentCalendar) -> ContentCalendar:
        """Lock the calendar as finalised (no further revisions).

        Args:
            calendar: The content calendar to finalise.

        Returns:
            The same calendar with ``is_finalised`` set to True.
        """
        from datetime import datetime

        calendar.is_finalised = True
        calendar.finalised_at = datetime.utcnow()
        logger.info("calendar_finalised", calendar_id=calendar.calendar_id)
        return calendar

    def _parse_entries(self, parsed: Optional[dict[str, Any]]) -> list[CalendarEntry]:
        """Convert a parsed LLM JSON dict into a list of CalendarEntry objects.

        Args:
            parsed: Dict containing an 'entries' key with a list of entry dicts.

        Returns:
            List of validated CalendarEntry instances.
        """
        if not parsed or "entries" not in parsed:
            return []

        entries: list[CalendarEntry] = []
        for raw in parsed["entries"]:
            try:
                platform = Platform(raw.get("platform", "linkedin"))
                fmt_str = raw.get("content_format", "short_post")
                try:
                    fmt = ContentFormat(fmt_str)
                except ValueError:
                    fmt = ContentFormat.SHORT_POST

                entries.append(
                    CalendarEntry(
                        entry_id=raw.get("entry_id", str(uuid.uuid4())),
                        day_number=int(raw.get("day_number", 1)),
                        platform=platform,
                        topic=raw.get("topic", "AI Technology"),
                        content_format=fmt,
                        scheduled_time=raw.get("scheduled_time", "09:00 AM"),
                        rationale=raw.get("rationale", ""),
                    )
                )
            except Exception as exc:
                logger.warning("calendar_entry_parse_error", error=str(exc), raw=raw)

        return entries
