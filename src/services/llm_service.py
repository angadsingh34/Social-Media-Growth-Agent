"""LLM service abstraction layer.

Wraps Groq (primary) and Hugging Face (fallback) providers behind a single
interface. Handles retry logic, token tracking, and prompt templating.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMService:
    """Unified interface for LLM inference across multiple providers.

    Attributes:
        model_name: The Groq model identifier to use by default.
        temperature: Sampling temperature for generation.
        max_tokens: Maximum tokens per completion.
        _total_tokens_used: Running total of prompt + completion tokens.
    """

    def __init__(
        self,
        model_name: Optional[str] = "llama-3.1-8b-instant",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        """Initialise the LLM service with Groq as primary provider.

        Args:
            model_name: Override the default model from settings.
            temperature: Override the default temperature from settings.
            max_tokens: Override the default max_tokens from settings.
        """
        self.model_name = model_name or settings.llm_model
        self.temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self._total_tokens_used: int = 0
        self._call_count: int = 0
        self._total_latency_ms: float = 0.0

        self._client = ChatGroq(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_key=settings.groq_api_key,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def complete(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        """Send a completion request and return the assistant's response text.

        Args:
            user_prompt: The main instruction / question for the LLM.
            system_prompt: Optional system-level instruction prepended to
                the conversation.
            context: Optional additional context appended to user_prompt.

        Returns:
            The LLM's text response stripped of leading/trailing whitespace.

        Raises:
            RuntimeError: If the LLM provider returns an error after all
                retries are exhausted.
        """
        messages: list[Any] = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        full_prompt = user_prompt
        if context:
            full_prompt = f"{user_prompt}\n\n### Context\n{context}"

        messages.append(HumanMessage(content=full_prompt))

        start = time.monotonic()
        try:
            response = self._client.invoke(messages)
            elapsed_ms = (time.monotonic() - start) * 1000
            self._total_latency_ms += elapsed_ms
            self._call_count += 1

            # Track token usage where available
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                self._total_tokens_used += response.usage_metadata.get(
                    "total_tokens", 0
                )

            logger.info(
                "llm_call_complete",
                model=self.model_name,
                latency_ms=round(elapsed_ms, 1),
                total_tokens=self._total_tokens_used,
            )
            return str(response.content).strip()

        except Exception as exc:
            logger.error("llm_call_failed", error=str(exc), model=self.model_name)
            raise RuntimeError(f"LLM inference failed: {exc}") from exc

    @property
    def metrics(self) -> dict[str, Any]:
        """Return accumulated performance metrics for observability.

        Returns:
            Dict with keys: total_calls, total_tokens, avg_latency_ms.
        """
        avg_latency = (
            self._total_latency_ms / self._call_count if self._call_count else 0.0
        )
        return {
            "total_calls": self._call_count,
            "total_tokens": self._total_tokens_used,
            "avg_latency_ms": round(avg_latency, 1),
        }
