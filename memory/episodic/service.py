from datetime import datetime

from memory.episodic.creator import EpisodicMemoryCreator
from memory.episodic.storage import EpisodicMemoryStore
from schemas.episodic_memory import (
    ChatHistoryMessage,
    EpisodeRecord,
)
from pydantic import BaseModel, ConfigDict, Field


class EpisodicConsolidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[EpisodeRecord] = Field(default_factory=list)
    error: str | None = None

    @property
    def created_any(self) -> bool:
        return bool(self.records)


class EpisodicMemoryService:
    """Coordinates post-session extraction, validation, and persistence."""

    def __init__(
        self,
        creator: EpisodicMemoryCreator | None = None,
        store: EpisodicMemoryStore | None = None,
    ) -> None:
        self.creator = creator or EpisodicMemoryCreator()
        self.store = store or EpisodicMemoryStore()

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
        try:
            for episode in extraction.episodes:
                records.append(self.store.create(episode, timestamp=timestamp))
        except Exception as exc:
            return EpisodicConsolidationResult(
                records=records,
                error=f"Episodic memory persistence failure: {str(exc)[:2000]}",
            )

        return EpisodicConsolidationResult(records=records)