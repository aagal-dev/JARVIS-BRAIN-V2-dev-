from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal


class JarvisBrainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failed", "partial"]

    output: Any | None = None

    error: str | None = None

    state: dict[str, Any] = Field(default_factory=dict)