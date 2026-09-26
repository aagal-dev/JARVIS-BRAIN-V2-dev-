from __future__ import annotations
import math
from typing import List

from schemas.memory_retrieval import MemoryRetrievalResult, MemoryRetrievalResultItem
from schemas.episodic_memory import EpisodeRecord

class FallbackRetriever:
    """Provides a simple dense‑vector fallback when Qdrant is unavailable.

    The class mirrors the logic that used to live inside ``MemoryRetrieval._fallback_search``.
    It is deliberately isolated so that the core retrieval module stays clean and the
    fallback implementation can be unit‑tested independently.
    """

    def __init__(self, cohere_client, store):
        self.cohere = cohere_client
        self.store = store

    def search(self, query: str, limit: int = 5) -> MemoryRetrievalResult:
        """Embed ``query`` and all active episodes, compute cosine similarity,
        and return the top *limit* matches.
        """
        # Embed the query – any embedding error results in an empty result set.
        try:
            query_vec = self.cohere.embed_query(query)
        except Exception:
            return MemoryRetrievalResult(query=query, results=[])

        matches: List[MemoryRetrievalResultItem] = []
        for record in self.store.list_active():
            if not record.episode:
                continue
            try:
                ep_vec = self.cohere.embed_document(record.episode.summary)
            except Exception:
                continue
            # cosine similarity
            dot = sum(q * e for q, e in zip(query_vec, ep_vec))
            norm_q = math.sqrt(sum(q * q for q in query_vec))
            norm_e = math.sqrt(sum(e * e for e in ep_vec))
            score = dot / (norm_q * norm_e) if norm_q and norm_e else 0.0
            matches.append(
                MemoryRetrievalResultItem(id=record.id, score=score, episode=record.episode)
            )
        # Sort by descending similarity and truncate to ``limit``
        matches.sort(key=lambda item: item.score, reverse=True)
        return MemoryRetrievalResult(query=query, results=matches[:limit])
