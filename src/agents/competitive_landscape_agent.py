"""Competitive Landscape Agent (FR-2).

Identifies 3-5 competitor profiles in the same niche, analyses them using
the same framework as the Profile Intelligence Agent, and synthesises the
findings into a CompetitiveAnalysisReport highlighting content gaps,
engagement-driving formats, and strategic opportunities.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.agents.profile_intelligence_agent import ProfileIntelligenceAgent
from src.models.schemas import (
    CompetitiveAnalysisReport,
    ContentFormat,
    ContentGap,
    Platform,
    ProfileIntelligenceReport,
)
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService
from src.utils.helpers import safe_json_parse
from src.utils.mock_data import MOCK_COMPETITOR_PROFILES

_COMPETITOR_DISCOVERY_SYSTEM = """You are a social media strategist with deep knowledge of
the AI/tech content ecosystem. Return ONLY valid JSON."""

_COMPETITOR_DISCOVERY_TEMPLATE = """Given a user's profile, identify 3-5 competitor or peer
content creators in the same niche who the user should benchmark against.

User Profile Summary:
{profile_summary}

Return JSON:
{{
  "competitors": [
    {{
      "platform": "linkedin" or "twitter",
      "username": "<handle>",
      "rationale": "<one sentence explaining why they are a relevant benchmark>"
    }}
  ]
}}"""

_SYNTHESIS_SYSTEM = """You are a senior content strategist. Synthesise competitive
intelligence into actionable insights. Return ONLY valid JSON."""

_SYNTHESIS_TEMPLATE = """Given the following competitor analyses and user profile, identify
content gaps, strategic opportunities, and niche trends.

User Profile:
{user_profile}

Competitor Analyses (JSON):
{competitor_analyses}

Return JSON:
{{
  "content_gaps": [
    {{
      "topic_or_format": "<string>",
      "competitor_name": "<string>",
      "engagement_signal": "<string>",
      "recommendation": "<string>"
    }}
  ],
  "trending_topics_in_niche": [<list of 5-7 trending topic strings>],
  "high_engagement_formats_in_niche": [<list of format strings>],
  "strategic_opportunities": [<list of 3-5 actionable opportunity strings>]
}}"""


class CompetitiveLandscapeAgent(BaseAgent):
    """Discovers and analyses competitor profiles and produces a benchmark report.

    Attributes:
        profile_agent: Reused Profile Intelligence Agent for competitor analysis.
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the Competitive Landscape Agent.

        Args:
            llm: Shared LLM service.
            retriever: Shared RAG retriever.
        """
        super().__init__("competitive_landscape", llm=llm, retriever=retriever)
        self.profile_agent = ProfileIntelligenceAgent(llm=llm, retriever=retriever)

    def run(
        self,
        user_profile_report: ProfileIntelligenceReport,
        use_mock: bool = True,
        **kwargs: Any,
    ) -> CompetitiveAnalysisReport:
        """Execute competitive landscape analysis.

        Args:
            user_profile_report: The user's previously generated profile report.
            use_mock: When True uses fixture competitor profiles; when False
                attempts live competitor discovery via the LLM.

        Returns:
            A fully populated CompetitiveAnalysisReport.
        """
        self.logger.info(
            "competitive_analysis_start",
            username=user_profile_report.username,
        )

        # Step 1: Discover or load competitor list
        competitors_raw = self._discover_competitors(user_profile_report, use_mock)

        # Step 2: Analyse each competitor
        competitor_reports = self._analyse_competitors(competitors_raw, use_mock)

        # Step 3: Synthesise into gap / opportunity report
        report = self._synthesise(user_profile_report, competitor_reports)

        # Step 4: Index competitive insights into RAG
        self.retriever.index_competitive_report(
            report.model_dump(), user_profile_report.username
        )

        self.logger.info(
            "competitive_analysis_complete",
            username=user_profile_report.username,
            competitors_analysed=len(competitor_reports),
            gaps_found=len(report.content_gaps),
        )
        return report

    def _discover_competitors(
        self,
        user_report: ProfileIntelligenceReport,
        use_mock: bool,
    ) -> list[dict[str, Any]]:
        """Identify competitor profiles to benchmark.

        Args:
            user_report: User's profile intelligence report.
            use_mock: Use mock competitor profiles if True.

        Returns:
            List of competitor descriptor dicts (platform, username, rationale).
        """
        if use_mock:
            return [
                {
                    "platform": p["platform"],
                    "username": p["username"],
                    "rationale": "Mock competitor",
                }
                for p in MOCK_COMPETITOR_PROFILES
            ]

        summary = (
            f"Name: {user_report.full_name}\n"
            f"Topics: {', '.join(user_report.top_topics)}\n"
            f"Summary: {user_report.content_dna_summary}"
        )
        prompt = _COMPETITOR_DISCOVERY_TEMPLATE.format(profile_summary=summary)
        raw = self.llm.complete(prompt, system_prompt=_COMPETITOR_DISCOVERY_SYSTEM)
        parsed = safe_json_parse(raw)
        if parsed and "competitors" in parsed:
            return parsed["competitors"]
        return []

    def _analyse_competitors(
        self,
        competitors_raw: list[dict[str, Any]],
        use_mock: bool,
    ) -> list[dict[str, Any]]:
        """Run profile analysis on each discovered competitor.

        Args:
            competitors_raw: List of competitor descriptor dicts.
            use_mock: Forward to profile agent's data-fetching mode.

        Returns:
            List of competitor profile analysis dicts.
        """
        results = []
        mock_profiles = {p["username"]: p for p in MOCK_COMPETITOR_PROFILES}

        for comp in competitors_raw[:5]:  # cap at 5
            username = comp.get("username", "")
            platform_str = comp.get("platform", "linkedin")
            try:
                platform = Platform(platform_str)
            except ValueError:
                platform = Platform.LINKEDIN

            if use_mock and username in mock_profiles:
                results.append(mock_profiles[username])
            else:
                try:
                    report = self.profile_agent.run(
                        platform=platform, username=username
                    )
                    results.append(report.model_dump())
                except Exception as exc:
                    self.logger.warning(
                        "competitor_analysis_failed",
                        username=username,
                        error=str(exc),
                    )
        return results

    def _synthesise(
        self,
        user_report: ProfileIntelligenceReport,
        competitor_reports: list[dict[str, Any]],
    ) -> CompetitiveAnalysisReport:
        """Synthesise user and competitor data into the final analysis report.

        Args:
            user_report: User's profile intelligence report.
            competitor_reports: List of competitor profile dicts.

        Returns:
            Validated CompetitiveAnalysisReport.
        """
        user_str = json.dumps(user_report.model_dump(), indent=2, default=str)
        comp_str = json.dumps(competitor_reports, indent=2, default=str)
        prompt = _SYNTHESIS_TEMPLATE.format(
            user_profile=user_str, competitor_analyses=comp_str
        )
        raw = self.llm.complete(prompt, system_prompt=_SYNTHESIS_SYSTEM)
        parsed = safe_json_parse(raw) or {}

        gaps = [
            ContentGap(
                topic_or_format=g.get("topic_or_format", ""),
                competitor_name=g.get("competitor_name", ""),
                engagement_signal=g.get("engagement_signal", ""),
                recommendation=g.get("recommendation", ""),
            )
            for g in parsed.get("content_gaps", [])
        ]

        def _to_formats(raw_list: list) -> list[ContentFormat]:
            result = []
            for f in raw_list:
                try:
                    result.append(ContentFormat(f))
                except ValueError:
                    pass
            return result

        return CompetitiveAnalysisReport(
            user_username=user_report.username,
            analysed_competitors=[r.get("username", "") for r in competitor_reports],
            content_gaps=gaps,
            trending_topics_in_niche=parsed.get("trending_topics_in_niche", []),
            high_engagement_formats_in_niche=_to_formats(
                parsed.get("high_engagement_formats_in_niche", [])
            ),
            strategic_opportunities=parsed.get("strategic_opportunities", []),
        )
