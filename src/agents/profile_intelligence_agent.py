"""Profile Intelligence Agent (FR-1).

Analyses a social media profile's writing style, content themes, posting
cadence, format preferences, and engagement patterns. Outputs a structured
ProfileIntelligenceReport that feeds downstream agents and the RAG store.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.models.schemas import (
    ContentFormat,
    Platform,
    ProfileIntelligenceReport,
    WritingStyleProfile,
)
from src.rag.retriever import RAGRetriever
from src.services.linkedin_service import LinkedInService
from src.services.llm_service import LLMService
from src.services.twitter_service import TwitterService
from src.utils.helpers import safe_json_parse
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_ANALYSIS_SYSTEM_PROMPT = """You are an expert social media content analyst specialising in
professional and technical content on LinkedIn and X (Twitter).
Your role is to deeply analyse a profile's content DNA and return a structured JSON report.
Always return ONLY valid JSON — no markdown, no preamble."""

_ANALYSIS_USER_TEMPLATE = """Analyse the following social media profile data and produce a
comprehensive Profile Intelligence Report in JSON.

Profile Data:
{profile_data}

Return a JSON object with EXACTLY these keys:
{{
  "writing_style": {{
    "tone": "<string: e.g. 'authoritative', 'casual', 'technical', 'inspirational'>",
    "vocabulary_level": "<string: 'technical', 'accessible', 'mixed'>",
    "avg_post_length": <integer: estimated average word count per post>,
    "uses_emojis": <boolean>,
    "uses_hashtags": <boolean>,
    "signature_phrases": [<up to 3 example phrases or empty list>]
  }},
  "top_topics": [<list of 5-8 topic strings>],
  "content_formats": [<list using: short_post, thread, article, listicle, poll, carousel>],
  "posting_cadence_per_week": <float>,
  "high_engagement_topics": [<list of 3-5 topics that get the most engagement>],
  "high_engagement_formats": [<list of formats with best engagement>],
  "content_dna_summary": "<2-3 sentence narrative of this profile's unique content identity>"
}}"""


class ProfileIntelligenceAgent(BaseAgent):
    """Analyses a user's social media profile and produces a structured report.

    Uses the platform-appropriate service to fetch raw profile data, then
    leverages the LLM to extract structured insights.

    Attributes:
        linkedin_svc: LinkedIn data fetching service.
        twitter_svc: Twitter/X data fetching service.
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the Profile Intelligence Agent.

        Args:
            llm: Shared LLM service instance.
            retriever: Shared RAG retriever instance.
        """
        super().__init__("profile_intelligence", llm=llm, retriever=retriever)
        self.linkedin_svc = LinkedInService()
        self.twitter_svc = TwitterService()

    def run(
        self,
        platform: Platform,
        username: str,
        **kwargs: Any,
    ) -> ProfileIntelligenceReport:
        """Execute profile analysis and return a ProfileIntelligenceReport.

        Args:
            platform: The target social platform (linkedin or twitter).
            username: The profile username / handle to analyse.

        Returns:
            A fully populated ProfileIntelligenceReport.

        Raises:
            ValueError: If the platform is not supported.
        """
        self.logger.info("profile_analysis_start", platform=platform, username=username)

        # Step 1: Fetch raw profile data
        raw_profile = self._fetch_raw_profile(platform, username)

        # Step 2: Invoke LLM for structured analysis
        profile_json_str = json.dumps(raw_profile, indent=2, default=str)
        prompt = _ANALYSIS_USER_TEMPLATE.format(profile_data=profile_json_str)
        raw_response = self.llm.complete(
            user_prompt=prompt,
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
        )

        # Step 3: Parse LLM JSON output
        parsed = safe_json_parse(raw_response)
        if not parsed or not isinstance(parsed, dict):
            self.logger.warning("llm_json_parse_failed_using_defaults")
            parsed = self._build_fallback_analysis(raw_profile)

        # Step 4: Construct typed report
        report = self._build_report(platform, username, raw_profile, parsed)

        # Step 5: Index into RAG store
        self.retriever.index_profile_report(report.model_dump(), username)

        self.logger.info(
            "profile_analysis_complete",
            username=username,
            topics=report.top_topics[:3],
        )
        return report

    def _fetch_raw_profile(self, platform: Platform, username: str) -> dict[str, Any]:
        """Dispatch profile fetch to the appropriate service.

        Args:
            platform: Target platform.
            username: Profile identifier.

        Returns:
            Raw profile dict from the platform service.
        """
        if platform == Platform.LINKEDIN:
            return self.linkedin_svc.fetch_profile(username)
        elif platform == Platform.TWITTER:
            return self.twitter_svc.fetch_profile(username)
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    def _build_report(
        self,
        platform: Platform,
        username: str,
        raw: dict[str, Any],
        analysis: dict[str, Any],
    ) -> ProfileIntelligenceReport:
        """Merge raw profile data with LLM analysis into a typed report.

        Args:
            platform: Source platform.
            username: Profile username.
            raw: Raw profile dict.
            analysis: Parsed LLM analysis dict.

        Returns:
            Validated ProfileIntelligenceReport instance.
        """
        ws_data = analysis.get("writing_style", {})
        writing_style = WritingStyleProfile(
            tone=ws_data.get("tone", "professional"),
            vocabulary_level=ws_data.get("vocabulary_level", "technical"),
            avg_post_length=int(ws_data.get("avg_post_length", 100)),
            uses_emojis=bool(ws_data.get("uses_emojis", False)),
            uses_hashtags=bool(ws_data.get("uses_hashtags", True)),
            signature_phrases=ws_data.get("signature_phrases", []),
        )

        def _to_formats(raw_list: list) -> list[ContentFormat]:
            result = []
            for f in raw_list:
                try:
                    result.append(ContentFormat(f))
                except ValueError:
                    pass
            return result

        return ProfileIntelligenceReport(
            platform=platform,
            username=username,
            full_name=raw.get("full_name", username),
            follower_count=raw.get("follower_count", 0),
            writing_style=writing_style,
            top_topics=analysis.get("top_topics", []),
            content_formats=_to_formats(analysis.get("content_formats", [])),
            posting_cadence_per_week=float(
                analysis.get("posting_cadence_per_week", 0.0)
            ),
            high_engagement_topics=analysis.get("high_engagement_topics", []),
            high_engagement_formats=_to_formats(
                analysis.get("high_engagement_formats", [])
            ),
            content_dna_summary=analysis.get(
                "content_dna_summary",
                f"A professional in {raw.get('headline', 'their field')}.",
            ),
        )

    def _build_fallback_analysis(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Build a minimal analysis dict when LLM parsing fails.

        Args:
            raw: Raw profile data dict.

        Returns:
            A safe fallback analysis dict.
        """
        return {
            "writing_style": {
                "tone": "professional",
                "vocabulary_level": "technical",
                "avg_post_length": 120,
                "uses_emojis": False,
                "uses_hashtags": True,
                "signature_phrases": [],
            },
            "top_topics": raw.get("primary_topics", ["AI", "technology"])[:8],
            "content_formats": raw.get("content_formats", ["short_post"]),
            "posting_cadence_per_week": raw.get("posting_frequency_per_week", 3.0),
            "high_engagement_topics": raw.get("primary_topics", [])[:3],
            "high_engagement_formats": ["short_post", "thread"],
            "content_dna_summary": raw.get("bio", "A professional content creator."),
        }
