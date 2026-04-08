"""Copy Agent (FR-4) — generates body text for each scheduled post.

Calibrates output to the user's writing style and platform conventions.
Grounds generation via RAG-retrieved context from profile and competitive reports.
"""

from __future__ import annotations

from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.models.schemas import CalendarEntry, Platform
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService

_COPY_SYSTEM = """You are an expert social media copywriter who mirrors the author's authentic
voice exactly. Write only the post text — no commentary, no title, no hashtags."""

_COPY_TEMPLATE = """Write a {platform} post on the topic: "{topic}"
Content format: {content_format}

Author's writing style context:
{context}

Platform constraints:
- LinkedIn: Professional tone, up to 3000 characters, can use line breaks for readability.
- Twitter/X: Conversational, ≤280 characters per tweet. For threads, write each tweet
  separated by '---TWEET---'.

Produce ONLY the final post text, faithful to the author's voice."""


class CopyAgent(BaseAgent):
    """Generates post body copy calibrated to the user's content DNA.

    Attributes:
        None beyond BaseAgent.
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the Copy Agent.

        Args:
            llm: Shared LLM service.
            retriever: Shared RAG retriever for style/topic context.
        """
        super().__init__("copy", llm=llm, retriever=retriever)

    def run(
        self,
        entry: CalendarEntry,
        username: str,
        instructions: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate body copy for a calendar entry.

        Args:
            entry: The CalendarEntry specifying topic, platform, and format.
            username: The user's username (used for RAG retrieval).
            instructions: Optional targeted revision instructions.

        Returns:
            The generated post body copy as a string.
        """
        query = f"{entry.topic} {entry.content_format.value} writing style"
        context = self.retriever.retrieve_context(query, top_k=5)

        platform_name = entry.platform.value.capitalize()
        prompt = _COPY_TEMPLATE.format(
            platform=platform_name,
            topic=entry.topic,
            content_format=entry.content_format.value,
            context=context
            or "No prior context available — use a professional, technical tone.",
        )

        if instructions:
            prompt += f"\n\nRevision instructions: {instructions}"

        body_copy = self.llm.complete(user_prompt=prompt, system_prompt=_COPY_SYSTEM)
        self.logger.info(
            "copy_generated",
            entry_id=entry.entry_id,
            platform=entry.platform,
            chars=len(body_copy),
        )
        return body_copy
