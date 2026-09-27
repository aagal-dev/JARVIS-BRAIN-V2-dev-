from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectorExecutionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: str
    query: str
    status: str
    result_count: int = 0


class ResearchResult(BaseModel):
    """Small, runtime-safe envelope around the research pipeline output."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    status: Literal["success", "partial", "failed"]
    query: str
    synthesis: str | dict[str, Any] | None = None
    connector_executions: list[ConnectorExecutionSummary] = Field(
        default_factory=list
    )
    errors: list[str] = Field(default_factory=list)