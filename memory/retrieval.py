from typing import Any

from integrations.qdrant_client import QdrantClient
from integrations.voyage_client import VoyageClient
from memory.episodic.storage import EpisodicMemoryStore
from schemas.episodic_memory import EpisodeRecord
from schemas.memory_retrieval import (
    MemoryRetrievalResult,
    MemoryRetrievalResultItem,
)


class MemoryRetrieval:
    """Owns embedding, hybrid search, canonical mapping, and indexing."""

    def __init__(
        self,
        voyage_client: VoyageClient | None = None,
        qdrant_client: QdrantClient | None = None,
        store: EpisodicMemoryStore | None = None,
    ) -> None:
        self.voyage = voyage_client or VoyageClient()
        self.qdrant = qdrant_client or QdrantClient()
        self.store = store or EpisodicMemoryStore()

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        query_filter: dict[str, Any] | None = None,
    ) -> MemoryRetrievalResult:
        if not isinstance(query, str) or not query.strip():
            return MemoryRetrievalResult(
                query=query if isinstance(query, str) else "",
                error="Memory retrieval requires a non-empty query.",
            )
        if limit <= 0:
            return MemoryRetrievalResult(
                query=query,
                error="Memory retrieval limit must be positive.",
            )

        try:
            dense_vector = self.voyage.embed_query(query)
            points = self.qdrant.hybrid_search(
                query=query,
                dense_vector=dense_vector,
                limit=limit,
                query_filter=query_filter,
            )
            ids = [self._point_id(point) for point in points]
            canonical = self.store.get_active_by_ids(
                [point_id for point_id in ids if point_id]
            )
            results: list[MemoryRetrievalResultItem] = []
            for point, point_id in zip(points, ids):
                if point_id is None:
                    continue
                record = canonical.get(point_id)
                if record is None or record.episode is None:
                    continue
                results.append(
                    MemoryRetrievalResultItem(
                        id=record.id,
                        score=self._score(point),
                        source="hybrid",
                        episode=record.episode,
                    )
                )
            return MemoryRetrievalResult(query=query, results=results)
        except Exception as exc:
            return MemoryRetrievalResult(
                query=query,
                error=f"Memory retrieval failed: {str(exc)[:2000]}",
            )

    def index_record(self, record: EpisodeRecord) -> str | None:
        """Index after canonical persistence; return a non-fatal error string."""
        try:
            target_id = record.target_id or record.id
            if record.action == "delete":
                self.qdrant.delete_episode(target_id)
                return None
            if record.episode is None:
                return "Episode indexing skipped because the payload is missing."

            dense_vector = self.voyage.embed_document(record.episode.summary)
            self.qdrant.upsert_episode(
                episode_id=target_id,
                summary=record.episode.summary,
                dense_vector=dense_vector,
                payload={
                    "type": record.episode.type,
                    "tags": record.episode.tags,
                },
            )
            return None
        except Exception as exc:
            return f"Episode {record.id} was stored but not indexed: {str(exc)[:2000]}"

    def rebuild_index(self) -> list[str]:
        """Rebuild the derived Qdrant index from canonical active episodes."""
        errors: list[str] = []
        for record in self.store.list_active():
            error = self.index_record(record)
            if error:
                errors.append(error)
        return errors

    @staticmethod
    def _point_id(point: dict[str, Any]) -> str | None:
        point_id = point.get("id")
        if point_id is None:
            payload = point.get("payload")
            if isinstance(payload, dict):
                point_id = payload.get("episode_id")
        return str(point_id) if point_id is not None else None

    @staticmethod
    def _score(point: dict[str, Any]) -> float:
        score = point.get("score", 0.0)
        try:
            return float(score)
        except (TypeError, ValueError):
            return 0.0