"""Hashtag Agent (FR-4) — generates optimised hashtag sets for each post.

Uses topic, platform, engagement patterns from the RAG store, and niche
trends to produce relevant, non-spammy hashtag collections.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.models.schemas import CalendarEntry, Platform
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService

_HASHTAG_SYSTEM = """You are a social media growth expert specialising in hashtag strategy.
Return ONLY a comma-separated list of hashtags (with # prefix), no explanations."""

_HASHTAG_TEMPLATE = """Generate optimal hashtags for a {platform} post.

Topic: {topic}
Content format: {content_format}

Relevant niche and engagement context:
{context}

Rules:
- LinkedIn: 3-5 hashtags, mix of broad (#AI) and specific (#LangGraph)
- Twitter/X: 1-3 hashtags maximum, only the most impactful

Return ONLY comma-separated hashtags, e.g.: #AI, #LangChain, #Python"""


class HashtagAgent(BaseAgent):
    """Generates platform-optimised hashtags for each post.

    Attributes:
        None beyond BaseAgent.
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the Hashtag Agent.

        Args:
            llm: Shared LLM service.
            retriever: Shared RAG retriever for niche/trend context.
        """
        super().__init__("hashtag", llm=llm, retriever=retriever)

    def run(
        self,
        entry: CalendarEntry,
        instructions: Optional[str] = None,
        **kwargs: Any,
    ) -> list[str]:
        """Generate hashtags for a calendar entry.

        Args:
            entry: The target CalendarEntry.
            instructions: Optional targeted regeneration instructions.

        Returns:
            List of hashtag strings (each prefixed with #).
        """
        query = f"trending hashtags {entry.topic} {entry.platform.value}"
        context = self.retriever.retrieve_context(query, top_k=4)

        prompt = _HASHTAG_TEMPLATE.format(
            platform=entry.platform.value.capitalize(),
            topic=entry.topic,
            content_format=entry.content_format.value,
            context=context or "General AI/tech professional niche.",
        )
        if instructions:
            prompt += f"\n\nInstructions: {instructions}"

        raw = self.llm.complete(user_prompt=prompt, system_prompt=_HASHTAG_SYSTEM)
        hashtags = self._parse_hashtags(raw, entry.platform)

        self.logger.info(
            "hashtags_generated",
            entry_id=entry.entry_id,
            count=len(hashtags),
        )
        return hashtags

    def _parse_hashtags(self, raw: str, platform: Platform) -> list[str]:
        """Parse and validate hashtags from LLM output.

        Args:
            raw: Raw LLM output string.
            platform: Target platform for count enforcement.

        Returns:
            Cleaned list of hashtag strings.
        """
        tokens = re.split(r"[,\s]+", raw)
        hashtags = [t.strip() for t in tokens if t.strip().startswith("#")]
        # Enforce platform caps
        if platform == Platform.LINKEDIN:
            hashtags = hashtags[:5]
        elif platform == Platform.TWITTER:
            hashtags = hashtags[:3]
        return hashtags
