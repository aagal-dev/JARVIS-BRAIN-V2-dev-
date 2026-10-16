from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# Enums
# ============================================================

class OrchestratorNextStep(str, Enum):
    EXECUTE = "execute"
    RESPOND = "respond"
    STOP = "stop"


# ============================================================
# Orchestrator Action
# ============================================================

class OrchestratorAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(
        description=(
            "Exact namespaced MCP tool name from available_tools, in "
            "'server__tool' form."
        ),
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments matching the selected tool's input_schema exactly.",
    )


# ============================================================
# Conversation Agent Handoff
# ============================================================

class ConversationAgentHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_request: str = Field(
        description="The original user request or intended objective."
    )

    objective: str = Field(
        description=(
            "A concise objective describing what the Conversation Agent "
            "should accomplish in the final user-facing response."
        ),
    )


# ============================================================
# Main Orchestrator Result
# ============================================================

class OrchestratorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_step: Optional[OrchestratorNextStep] = Field(
        default=None,
        description=(
            "A scalar string containing exactly one workflow transition: "
            "'execute', 'respond', or 'stop'. Do not return an object."
        ),
    )

    conversation_agent_handoff: Optional[ConversationAgentHandoff] = Field(
        default=None,
        description=(
            "Minimal handoff from the orchestrator to the Conversation Agent. "
            "Runtime context is assembled separately and combined with this handoff."
        ),
    )

    actions: list[OrchestratorAction] = Field(
        default_factory=list,
        description=(
            "Sequential MCP tool calls to perform when next_step is execute."
        ),
    )

    error: Optional[str] = Field(
        default=None,
        description=(
            "Infrastructure/runtime field. The orchestrator must not intentionally "
            "populate this as an orchestration decision."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_transition(cls, values: Any) -> Any:
        """Flatten a nested transition object into the canonical result shape."""
        if not isinstance(values, dict):
            return values

        transition = values.get("next_step")
        if not isinstance(transition, dict):
            return values

        transition_type = transition.get("type")
        if transition_type not in {step.value for step in OrchestratorNextStep}:
            return values

        allowed_fields = {
            "type",
            "actions",
            "conversation_agent_handoff",
            "error",
        }
        if transition.keys() - allowed_fields:
            return values

        normalized = dict(values)
        normalized["next_step"] = transition_type
        for field in ("actions", "conversation_agent_handoff", "error"):
            if field not in transition:
                continue
            if field in normalized and normalized[field] != transition[field]:
                raise ValueError(
                    f"Conflicting '{field}' values in nested and top-level "
                    "orchestrator output."
                )
            normalized[field] = transition[field]

        return normalized

    @model_validator(mode="after")
    def validate_transition(self):
        if self.next_step is None:
            if self.error is None:
                raise ValueError("next_step is required unless an error is provided.")
            return self

        if self.next_step == OrchestratorNextStep.EXECUTE:
            if not self.actions:
                raise ValueError(
                    "next_step='execute' requires at least one action."
                )

            if self.conversation_agent_handoff is not None:
                raise ValueError(
                    "next_step='execute' must not provide "
                    "conversation_agent_handoff."
                )

        elif self.next_step == OrchestratorNextStep.RESPOND:
            if self.actions:
                raise ValueError(
                    "next_step='respond' requires actions to be empty."
                )

            if self.conversation_agent_handoff is None:
                raise ValueError(
                    "next_step='respond' requires conversation_agent_handoff."
                )

        elif self.next_step == OrchestratorNextStep.STOP:
            if self.actions:
                raise ValueError(
                    "next_step='stop' requires actions to be empty."
                )

            if self.conversation_agent_handoff is not None:
                raise ValueError(
                    "next_step='stop' must not provide conversation_agent_handoff."
                )

        return self