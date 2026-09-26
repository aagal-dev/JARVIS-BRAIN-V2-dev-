from datetime import datetime

from memory.episodic.creator import EpisodicMemoryCreator
from memory.episodic.storage import EpisodicMemoryStore
from memory.retrieval import MemoryRetrieval
from schemas.episodic_memory import (
    ChatHistoryMessage,
    EpisodeRecord,
)
from pydantic import BaseModel, ConfigDict, Field


class EpisodicConsolidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[EpisodeRecord] = Field(default_factory=list)
    error: str | None = None
    indexing_errors: list[str] = Field(default_factory=list)

    @property
    def created_any(self) -> bool:
        return bool(self.records)


class EpisodicMemoryService:
    """Coordinates post-session extraction, validation, and persistence."""

    def __init__(
        self,
        creator: EpisodicMemoryCreator | None = None,
        store: EpisodicMemoryStore | None = None,
        retrieval: MemoryRetrieval | None = None,
    ) -> None:
        self.creator = creator or EpisodicMemoryCreator()
        self.store = store or EpisodicMemoryStore()
        self.retrieval = retrieval or MemoryRetrieval(store=self.store)

    def consolidate(
        self,
        chat_history: list[ChatHistoryMessage],
        timestamp: datetime | None = None,
    ) -> EpisodicConsolidationResult:
        if not chat_history:
            return EpisodicConsolidationResult()

        # Retrieve relevant existing episodes for context
        recent_query = " ".join(
            msg["content"] for msg in chat_history[-5:] if msg.get("content")
        )
        existing_episodes: list[dict[str, Any]] = []
        if recent_query.strip():
            try:
                retrieval_result = self.retrieval.retrieve(recent_query, limit=10)
                if not retrieval_result.error:
                    existing_episodes = [
                        {
                            "id": item.id,
                            "type": item.episode.type,
                            "summary": item.episode.summary,
                            "state": item.episode.state,
                            "change": item.episode.change,
                            "outcome": item.episode.outcome,
                            "tags": item.episode.tags,
                        }
                        for item in retrieval_result.results
                        if item.episode
                    ]
            except Exception:
                pass  # Continue without existing episodes if retrieval fails

        try:
            extraction = self.creator.create(
                list(chat_history),
                relevant_context={
                    "episodic_memory": existing_episodes,
                    "semantic_memory": [],
                    "procedural_memory": [],
                },
            )
        except Exception as exc:
            return EpisodicConsolidationResult(
                error=f"Episodic memory creator failure: {str(exc)[:2000]}"
            )

        if extraction.error:
            return EpisodicConsolidationResult(error=extraction.error)

        if not extraction.should_create and not extraction.episodes:
            print("\nNo episode creation needed.")
            return EpisodicConsolidationResult()

        records: list[EpisodeRecord] = []
        indexing_errors: list[str] = []
        try:
            for episode in extraction.episodes:
                if episode.action == "delete" and episode.target_id:
                    record = self.store.delete(episode.target_id, timestamp=timestamp)
                    records.append(record)
                    # Delete from index
                    indexing_error = self.retrieval.index_record(record)
                    if indexing_error:
                        indexing_errors.append(indexing_error)
                elif episode.action == "update" and episode.target_id:
                    record = self.store.update(
                        episode.target_id, episode, timestamp=timestamp
                    )
                    records.append(record)
                    indexing_error = self.retrieval.index_record(record)
                    if indexing_error:
                        indexing_errors.append(indexing_error)
                elif episode.action == "create":
                    record = self.store.create(episode, timestamp=timestamp)
                    records.append(record)
                    indexing_error = self.retrieval.index_record(record)
                    if indexing_error:
                        indexing_errors.append(indexing_error)
                else:
                    # Invalid action/target_id combination - skip
                    indexing_errors.append(
                        f"Invalid episode action: {episode.action} (target_id={episode.target_id})"
                    )
        except Exception as exc:
            return EpisodicConsolidationResult(
                records=records,
                error=f"Episodic memory persistence failure: {str(exc)[:2000]}",
                indexing_errors=indexing_errors,
            )

        return EpisodicConsolidationResult(
            records=records,
            indexing_errors=indexing_errors,
        )

    def rebuild_index(self) -> list[str]:
        return self.retrieval.rebuild_index()