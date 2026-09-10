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

        try:
            extraction = self.creator.create(list(chat_history))
        except Exception as exc:
            return EpisodicConsolidationResult(
                error=f"Episodic memory creator failure: {str(exc)[:2000]}"
            )

        if extraction.error:
            return EpisodicConsolidationResult(error=extraction.error)

        if not extraction.should_create:
            print("\nNo episode creation needed.")
            return EpisodicConsolidationResult()

        records: list[EpisodeRecord] = []
        indexing_errors: list[str] = []
        try:
            for episode in extraction.episodes:
                record = self.store.create(episode, timestamp=timestamp)
                records.append(record)
                indexing_error = self.retrieval.index_record(record)
                if indexing_error:
                    indexing_errors.append(indexing_error)
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