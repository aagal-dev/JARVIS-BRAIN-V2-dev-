from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    step: str
    status: Literal[
        "pending",
        "in_progress",
        "completed",
    ] = "pending"


class RuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_request: str
    objective: str
    steps: list[RuntimeStep] = Field(default_factory=list)
    current_step_id: str | None = None

    @model_validator(mode="after")
    def validate_step_references(self) -> "RuntimeState":
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Runtime step IDs must be unique.")

        if self.current_step_id is not None and self.current_step_id not in step_ids:
            raise ValueError("current_step_id must reference an existing runtime step.")

        return self