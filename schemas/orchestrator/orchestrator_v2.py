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
            "The single best next workflow transition: execute MCP tool work, "
            "respond through the Conversation Agent, or terminate/suspend."
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