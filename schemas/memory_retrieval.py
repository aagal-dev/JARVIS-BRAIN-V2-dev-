from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.episodic_memory import EpisodicEpisode


class MemoryRetrievalResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    score: float
    source: Literal["hybrid", "dense", "sparse"] = "hybrid"
    episode: EpisodicEpisode

    def as_context(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "source": self.source,
            **self.episode.model_dump(),
        }


class MemoryRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    results: list[MemoryRetrievalResultItem] = Field(default_factory=list)
    error: str | None = None

    def as_context(self) -> list[dict[str, Any]]:
        return [result.as_context() for result in self.results]