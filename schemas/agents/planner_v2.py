from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlannerStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    step: str
    status: Literal[
        "pending",
        "in_progress",
        "completed",
    ] = "pending"


class PlannerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["direct", "planned"]
    objective: Optional[str] = None
    steps: list[PlannerStep] = Field(default_factory=list)
    error: Optional[str] = None

    @model_validator(mode="after")
    def validate_step_ids(self) -> "PlannerResult":
        step_ids = [step.id for step in self.steps]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Planner step IDs must be unique.")

        if self.mode == "direct":
            if self.objective is not None:
                raise ValueError(
                    "Direct mode requires objective=None."
                )

            if self.steps:
                raise ValueError(
                    "Direct mode requires no steps."
                )

        elif self.mode == "planned":
            if not self.objective:
                raise ValueError(
                    "Planned mode requires a non-empty objective."
                )

            if not self.steps:
                raise ValueError(
                    "Planned mode requires at least one step."
                )

        return self


class PlannerRelevantContext(TypedDict):
    episodic_memory: list[dict[str, Any]]
    chat_archives: list[dict[str, Any]]
    learned_knowledge: list[dict[str, Any]]


class PlannerState(TypedDict):
    user_request: str
    recent_conversations: list[dict[str, str]]
    relevant_context: PlannerRelevantContext
    environment_context: dict[str, Any]
    available_components: dict[str, Any]
    retrieval_errors: list[str]