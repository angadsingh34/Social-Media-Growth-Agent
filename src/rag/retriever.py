"""RAG Retriever: chunks analysis reports and assembles retrieval context.

Responsible for:
1. Chunking Profile Intelligence and Competitive Analysis reports into
   semantically coherent passages.
2. Indexing those passages in the FAISS vector store.
3. Providing a ``retrieve_context`` method used by content-generation agents
   to ground their prompts in relevant analysis findings.
"""

from __future__ import annotations

import re
from typing import Any

from src.rag.vector_store import FAISSVectorStore
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_CHUNK_SIZE = 300  # target characters per chunk
_CHUNK_OVERLAP = 50  # character overlap between adjacent chunks


def _chunk_text(
    text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping character-level chunks.

    Args:
        text: Input text to split.
        size: Maximum characters per chunk.
        overlap: Character overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    text = re.sub(r"\s+", " ", text).strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


class RAGRetriever:
    """Manages indexing and retrieval for the content generation pipeline.

    Attributes:
        vector_store: The underlying FAISS vector store instance.
    """

    def __init__(self) -> None:
        """Initialise the retriever with a fresh or persisted vector store."""
        self.vector_store = FAISSVectorStore()

    def index_profile_report(self, report: dict[str, Any], username: str) -> None:
        """Chunk and index a profile intelligence report.

        Args:
            report: A ProfileIntelligenceReport serialised as a dict.
            username: The profile username (used as metadata tag).
        """
        texts: list[str] = []
        tags: list[dict] = []

        # Narrative summary
        if summary := report.get("content_dna_summary"):
            chunks = _chunk_text(summary)
            texts.extend(chunks)
            tags.extend(
                [{"source": "profile_summary", "username": username}] * len(chunks)
            )

        # Top topics
        if topics := report.get("top_topics"):
            blob = "Top content topics: " + ", ".join(topics)
            texts.append(blob)
            tags.append({"source": "profile_topics", "username": username})

        # Writing style
        if ws := report.get("writing_style"):
            blob = (
                f"Writing style: tone={ws.get('tone')}, "
                f"vocabulary={ws.get('vocabulary_level')}, "
                f"avg_length={ws.get('avg_post_length')} words."
            )
            texts.append(blob)
            tags.append({"source": "writing_style", "username": username})

        self.vector_store.add_texts(texts, tags)
        logger.info("rag_profile_indexed", username=username, chunks=len(texts))

    def index_competitive_report(self, report: dict[str, Any], username: str) -> None:
        """Chunk and index a competitive analysis report.

        Args:
            report: A CompetitiveAnalysisReport serialised as a dict.
            username: The user's username (used as metadata tag).
        """
        texts: list[str] = []
        tags: list[dict] = []

        # Strategic opportunities
        for opp in report.get("strategic_opportunities", []):
            texts.append(f"Strategic opportunity: {opp}")
            tags.append({"source": "competitive_opportunity", "username": username})

        # Content gaps
        for gap in report.get("content_gaps", []):
            blob = (
                f"Content gap: {gap.get('topic_or_format')} — "
                f"{gap.get('recommendation')}"
            )
            texts.append(blob)
            tags.append({"source": "content_gap", "username": username})

        # Trending topics
        if trends := report.get("trending_topics_in_niche"):
            texts.append("Trending topics in niche: " + ", ".join(trends))
            tags.append({"source": "trending_topics", "username": username})

        self.vector_store.add_texts(texts, tags)
        logger.info("rag_competitive_indexed", username=username, chunks=len(texts))

    def retrieve_context(self, query: str, top_k: int = 5) -> str:
        """Retrieve and format relevant context passages for an agent prompt.

        Args:
            query: The semantic query reflecting what context is needed.
            top_k: Number of passages to retrieve.

        Returns:
            A formatted multi-line string of retrieved passages, or an empty
            string if the vector store contains no relevant entries.
        """
        results = self.vector_store.search(query, top_k=top_k)
        if not results:
            return ""

        passages = [f"[{r.get('source', 'context')}] {r['text']}" for r in results]
        return "\n\n".join(passages)
