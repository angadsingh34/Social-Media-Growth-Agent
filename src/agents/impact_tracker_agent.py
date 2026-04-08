"""Impact Tracker Agent (FR-7 Bonus) — polls engagement metrics and
proposes adaptive re-planning suggestions when post performance
deviates significantly from plan expectations.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.models.schemas import (
    AdaptiveSuggestion,
    ContentCalendar,
    Platform,
    PostEngagementSnapshot,
    PublishRecord,
)
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService
from src.services.linkedin_service import LinkedInService
from src.services.twitter_service import TwitterService
from src.utils.helpers import safe_json_parse

_ADAPTIVE_SYSTEM = """You are a data-driven content strategist. Analyse post performance
versus expectations and recommend calendar adjustments. Return ONLY valid JSON."""

_ADAPTIVE_TEMPLATE = """A published post has {performance_label} performance vs expectations.

Post details:
{post_details}

Engagement snapshot:
{snapshot}

Remaining calendar entries:
{remaining_entries}

If performance significantly deviates, suggest calendar adjustments.
Return JSON:
{{
  "observation": "<string: what you observed>",
  "suggested_action": "<string: what to change>",
  "affected_entry_ids": [<list of entry_id strings to adjust>]
}}"""


class ImpactTrackerAgent(BaseAgent):
    """Polls post engagement and proposes adaptive content strategy changes.

    Attributes:
        linkedin_svc: LinkedIn service for engagement polling.
        twitter_svc: Twitter service for engagement polling.
        deviation_threshold: Percentage deviation triggering a suggestion.
    """

    DEVIATION_THRESHOLD = 0.50  # 50% above or below expected to trigger

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the Impact Tracker Agent.

        Args:
            llm: Shared LLM service.
            retriever: Shared RAG retriever.
        """
        super().__init__("impact_tracker", llm=llm, retriever=retriever)
        self.linkedin_svc = LinkedInService()
        self.twitter_svc = TwitterService()

    def run(
        self,
        publish_record: PublishRecord,
        calendar: ContentCalendar,
        expected_likes: int = 100,
        **kwargs: Any,
    ) -> Optional[AdaptiveSuggestion]:
        """Check post engagement and optionally recommend calendar adjustments.

        Args:
            publish_record: The publish record of the post to analyse.
            calendar: The current content calendar for adaptation context.
            expected_likes: Baseline expected like count for deviation calc.

        Returns:
            An AdaptiveSuggestion if significant deviation is detected, else None.
        """
        snapshot = self._poll_engagement(publish_record)
        if snapshot is None:
            return None

        deviation = (snapshot.likes - expected_likes) / max(expected_likes, 1)
        if abs(deviation) < self.DEVIATION_THRESHOLD:
            self.logger.info(
                "impact_within_threshold",
                post_id=publish_record.post_id,
                deviation_pct=round(deviation * 100, 1),
            )
            return None

        performance_label = "outperforming" if deviation > 0 else "underperforming"
        remaining = [
            e.model_dump()
            for e in calendar.entries
            if e.review_status.value == "pending"
        ]

        prompt = _ADAPTIVE_TEMPLATE.format(
            performance_label=performance_label,
            post_details=json.dumps(publish_record.model_dump(), default=str),
            snapshot=json.dumps(snapshot.model_dump(), default=str),
            remaining_entries=json.dumps(remaining, default=str),
        )
        raw = self.llm.complete(prompt, system_prompt=_ADAPTIVE_SYSTEM)
        parsed = safe_json_parse(raw) or {}

        suggestion = AdaptiveSuggestion(
            based_on_post_id=publish_record.post_id,
            observation=parsed.get("observation", "Performance deviation detected."),
            suggested_action=parsed.get(
                "suggested_action", "Review remaining calendar entries."
            ),
            affected_entry_ids=parsed.get("affected_entry_ids", []),
        )
        self.logger.info(
            "adaptive_suggestion_generated",
            post_id=publish_record.post_id,
            deviation_pct=round(deviation * 100, 1),
        )
        return suggestion

    def _poll_engagement(
        self, record: PublishRecord
    ) -> Optional[PostEngagementSnapshot]:
        """Poll the platform for current engagement on a published post.

        Args:
            record: The publish record containing platform and post ID.

        Returns:
            A PostEngagementSnapshot, or None if polling fails.
        """
        if not record.platform_post_id:
            return None

        # Mock engagement data for demo purposes
        return PostEngagementSnapshot(
            post_id=record.post_id,
            platform_post_id=record.platform_post_id,
            platform=record.platform,
            likes=280,
            comments=45,
            shares=62,
            impressions=4500,
        )
