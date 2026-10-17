from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _planner_result_json_schema(
    schema: dict[str, Any],
    _model: type[BaseModel],
) -> None:
    """Keep successful model output strict while allowing internal error results."""
    mode_field = schema["properties"]["mode"]
    mode_value = next(
        value for value in mode_field["anyOf"] if value.get("type") == "string"
    )
    schema["properties"]["mode"] = {
        **mode_value,
        "title": mode_field["title"],
        "description": mode_field["description"],
    }
    schema["required"] = [*schema.get("required", []), "mode"]


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
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra=_planner_result_json_schema,
    )

    mode: Optional[Literal["direct", "planned"]] = Field(
        default=None,
        description=(
            "Required for a successful plan: exactly 'direct' or 'planned'. "
            "Absent only when error contains an agent/API failure."
        ),
    )
    objective: Optional[str] = None
    steps: list[PlannerStep] = Field(default_factory=list)
    error: Optional[str] = None

    @model_validator(mode="after")
    def validate_step_ids(self) -> "PlannerResult":
        if self.error:
            if self.mode is not None or self.objective is not None or self.steps:
                raise ValueError(
                    "Planner error results must not include planning state."
                )
            return self

        if self.mode is None:
            raise ValueError("Planner mode is required unless an error is provided.")

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
    available_tools: dict[str, Any]
    retrieval_errors: list[str]