"""Visual Concept Agent (FR-4) — generates image/graphic prompts for each post.

Produces detailed, platform-appropriate visual generation prompts. Optionally
calls a free-tier image generation API (e.g. Hugging Face Inference) to
produce actual images.
"""

from __future__ import annotations

from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.models.schemas import CalendarEntry
from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService

_VISUAL_SYSTEM = """You are a creative director specialising in social media visuals for
technical and professional content. Return only the image generation prompt."""

_VISUAL_TEMPLATE = """Generate a detailed image generation prompt for a social media post.

Post topic: {topic}
Platform: {platform}
Content format: {content_format}

Context from author's content DNA:
{context}

Requirements:
- Describe a clear, professional visual that reinforces the post topic
- Specify style (e.g. flat design, 3D render, infographic, photo-realistic)
- Include color palette guidance
- Mention any text overlays or data-visualisation elements if appropriate
- Keep the prompt under 200 words

Return ONLY the image generation prompt text."""


class VisualConceptAgent(BaseAgent):
    """Generates image/graphic prompts and optionally produces visuals.

    Attributes:
        None beyond BaseAgent.
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the Visual Concept Agent.

        Args:
            llm: Shared LLM service.
            retriever: Shared RAG retriever.
        """
        super().__init__("visual_concept", llm=llm, retriever=retriever)

    def run(
        self,
        entry: CalendarEntry,
        instructions: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a visual concept prompt for a calendar entry.

        Args:
            entry: The target CalendarEntry.
            instructions: Optional targeted regeneration instructions.

        Returns:
            Detailed image generation prompt string.
        """
        context = self.retriever.retrieve_context(
            f"visual style {entry.topic} professional", top_k=3
        )
        prompt = _VISUAL_TEMPLATE.format(
            topic=entry.topic,
            platform=entry.platform.value.capitalize(),
            content_format=entry.content_format.value,
            context=context or "Modern, clean professional aesthetic.",
        )
        if instructions:
            prompt += f"\n\nInstructions: {instructions}"

        visual_prompt = self.llm.complete(
            user_prompt=prompt, system_prompt=_VISUAL_SYSTEM
        )
        self.logger.info(
            "visual_prompt_generated",
            entry_id=entry.entry_id,
            chars=len(visual_prompt),
        )
        return visual_prompt
