from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatHistoryMessage(TypedDict):
    role: str
    content: str


class EpisodicMemoryCreatorState(TypedDict):
    chat_history: list[ChatHistoryMessage]
    relevant_context: dict[str, list[dict[str, Any]]]


class EpisodicEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    summary: str
    state: str | None = None
    change: str | None = None
    outcome: str | None = None
    learned_lesson: str | None = None
    importance: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_summary(self) -> "EpisodicEpisode":
        if not self.summary.strip():
            raise ValueError("Episode summary must not be empty.")
        return self


class EpisodicCreatorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_create: bool = False
    episodes: list[EpisodicEpisode] = Field(default_factory=list)
    error: Optional[str] = None

    @model_validator(mode="after")
    def validate_decision(self) -> "EpisodicCreatorResult":
        if not self.should_create and self.episodes:
            raise ValueError(
                "A non-memory-worthy session must not contain episodes."
            )
        return self


class EpisodeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    timestamp: datetime
    action: Literal["create", "update", "delete"]
    target_id: str | None = None
    episode: EpisodicEpisode | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "EpisodeRecord":
        if self.action in {"create", "update"} and self.episode is None:
            raise ValueError(
                f"Episode action '{self.action}' requires an episode payload."
            )
        if self.action in {"update", "delete"} and not self.target_id:
            raise ValueError(
                f"Episode action '{self.action}' requires target_id."
            )
        return self