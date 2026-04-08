"""Abstract base class for all specialised agents.

Enforces a consistent interface across the agent pool and provides shared
utilities: LLM access, RAG retrieval, structured logging, and metrics.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.rag.retriever import RAGRetriever
from src.services.llm_service import LLMService
from src.utils.logging_config import get_logger


class BaseAgent(ABC):
    """Abstract base for all pipeline agents.

    Attributes:
        name: Human-readable agent identifier used in logs.
        llm: LLM service instance for inference.
        retriever: RAG retriever for grounded context.
        logger: Structured logger bound to agent name.
        _runs: Number of times ``run`` has been called.
        _total_ms: Cumulative execution time in milliseconds.
    """

    def __init__(
        self,
        name: str,
        llm: Optional[LLMService] = None,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        """Initialise the base agent.

        Args:
            name: Agent identifier string.
            llm: Shared or dedicated LLM service. A new instance is created
                if not provided.
            retriever: Shared RAG retriever. A new instance is created if
                not provided.
        """
        self.name = name
        self.llm = llm or LLMService()
        self.retriever = retriever or RAGRetriever()
        self.logger = get_logger(f"agent.{name}")
        self._runs: int = 0
        self._total_ms: float = 0.0

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the agent's primary task.

        Subclasses must implement this method.

        Args:
            **kwargs: Agent-specific keyword arguments.

        Returns:
            Agent-specific output (typed in subclass docstrings).
        """
        ...

    def _timed_run(self, **kwargs: Any) -> Any:
        """Wrap ``run`` with execution timing and logging.

        Args:
            **kwargs: Forwarded to ``run``.

        Returns:
            The result from ``run``.
        """
        start = time.monotonic()
        try:
            result = self.run(**kwargs)
            elapsed = (time.monotonic() - start) * 1000
            self._total_ms += elapsed
            self._runs += 1
            self.logger.info(
                "agent_run_complete",
                agent=self.name,
                latency_ms=round(elapsed, 1),
                total_runs=self._runs,
            )
            return result
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            self.logger.error(
                "agent_run_failed",
                agent=self.name,
                error=str(exc),
                latency_ms=round(elapsed, 1),
            )
            raise

    @property
    def metrics(self) -> dict[str, Any]:
        """Return agent performance metrics.

        Returns:
            Dict with: agent_name, total_runs, avg_latency_ms, llm_metrics.
        """
        avg_ms = self._total_ms / self._runs if self._runs else 0.0
        return {
            "agent_name": self.name,
            "total_runs": self._runs,
            "avg_latency_ms": round(avg_ms, 1),
            "llm_metrics": self.llm.metrics,
        }
