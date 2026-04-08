"""FAISS-backed vector store for RAG-grounded content generation.

Embeds chunked analysis reports (profile intelligence, competitive analysis)
and persists the index to disk for reuse across pipeline runs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import get_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

_EMBEDDING_DIM = 384  # matches all-MiniLM-L6-v2


class FAISSVectorStore:
    """Simple FAISS flat-L2 vector store with sentence-transformer embeddings.

    Supports upsert, similarity search, and disk persistence.

    Attributes:
        store_path: Directory path for persisting the FAISS index and metadata.
        model: SentenceTransformer instance for embedding.
        index: FAISS IndexFlatL2 instance.
        metadata: List of text chunks aligned with FAISS index rows.
    """

    def __init__(self, store_path: Optional[str] = None) -> None:
        """Initialise the vector store, loading from disk if available.

        Args:
            store_path: Override the default path from settings.
        """
        self.store_path = Path(store_path or settings.vector_store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        logger.info("loading_embedding_model", model=settings.embedding_model)
        self.model = SentenceTransformer(settings.embedding_model)

        index_file = self.store_path / "index.faiss"
        meta_file = self.store_path / "metadata.json"

        if index_file.exists() and meta_file.exists():
            logger.info("vector_store_loading_from_disk", path=str(self.store_path))
            self.index = faiss.read_index(str(index_file))
            with open(meta_file, "r", encoding="utf-8") as f:
                self.metadata: list[dict] = json.load(f)
        else:
            self.index = faiss.IndexFlatL2(_EMBEDDING_DIM)
            self.metadata = []

    def add_texts(
        self, texts: list[str], meta_tags: Optional[list[dict]] = None
    ) -> None:
        """Embed and add a list of text chunks to the vector store.

        Args:
            texts: Text chunks to embed and index.
            meta_tags: Optional list of metadata dicts (same length as texts)
                to store alongside each embedding for retrieval context.
        """
        if not texts:
            return

        embeddings = self.model.encode(texts, normalize_embeddings=True)
        vectors = np.array(embeddings, dtype="float32")
        self.index.add(vectors)

        for i, text in enumerate(texts):
            tag = meta_tags[i] if meta_tags and i < len(meta_tags) else {}
            self.metadata.append({"text": text, **tag})

        self._persist()
        logger.info(
            "vector_store_texts_added", count=len(texts), total=self.index.ntotal
        )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve the top-k most similar chunks for a query string.

        Args:
            query: The semantic search query.
            top_k: Number of results to return.

        Returns:
            List of metadata dicts (each containing at minimum a 'text' key)
            sorted by ascending L2 distance.
        """
        if self.index.ntotal == 0:
            return []

        query_vec = self.model.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype="float32")

        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.metadata):
                entry = dict(self.metadata[idx])
                entry["distance"] = float(dist)
                results.append(entry)

        return results

    def _persist(self) -> None:
        """Save the FAISS index and metadata to disk."""
        faiss.write_index(self.index, str(self.store_path / "index.faiss"))
        with open(self.store_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def clear(self) -> None:
        """Reset the index and metadata (useful between pipeline runs)."""
        self.index = faiss.IndexFlatL2(_EMBEDDING_DIM)
        self.metadata = []
        self._persist()
        logger.info("vector_store_cleared")
