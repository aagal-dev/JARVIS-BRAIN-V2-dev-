from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# Enums
# ============================================================

class OrchestratorNextStep(str, Enum):
    EXECUTE = "execute"
    RESPOND = "respond"
    STOP = "stop"


class ActionType(str, Enum):
    AGENT = "agent"
    SUBSYSTEM = "subsystem"


# ============================================================
# Action Context
# ============================================================

class ActionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: Optional[str] = Field(
        default=None,
        description=(
            "Temporal reference relevant to the action when the task depends "
            "on a specific date or time; otherwise null."
        ),
    )

    conversation_summary: str = Field(
        default="",
        description=(
            "Concise summary of conversation information relevant to executing "
            "this action. Do not copy the full conversation."
        ),
    )

    relevant_prior_context: list[str] = Field(
        default_factory=list,
        description=(
            "Relevant prior facts, findings, decisions, or context needed by "
            "the target component. Keep this task-specific and grounded."
        ),
    )


# ============================================================
# Action Input
# ============================================================

class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_request: str = Field(
        description="The original user request relevant to this action."
    )

    goal: str = Field(
        description=(
            "A concise, grounded statement of what the target component must "
            "accomplish now."
        ),
    )

    context: ActionContext = Field(
        default_factory=ActionContext,
        description=(
            "Task-specific context required to execute the action. "
            "Do not duplicate unnecessary runtime state."
        ),
    )


# ============================================================
# Orchestrator Action
# ============================================================

class OrchestratorAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActionType = Field(
        description="Whether the target component is an agent or subsystem."
    )

    component: str = Field(
        description=(
            "Exact registered component name. Must match a component listed "
            "in available_components."
        ),
    )

    input: ActionInput = Field(
        description="Structured input required by the selected component."
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

    next_step: OrchestratorNextStep = Field(
        description=(
            "The single best next workflow transition: execute component work, "
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
            "Sequential component work to perform when next_step is execute."
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