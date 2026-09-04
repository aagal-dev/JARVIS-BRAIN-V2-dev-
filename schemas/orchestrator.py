from typing import Any, Literal, Optional 

from pydantic import BaseModel, ConfigDict, Field


class OrchestratorAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["agent", "subsystem"]
  
    component: str = Field(
        description="Registered agent or subsystem that should execute the action."
    )

    task: str = Field(
        description="Concrete task the selected component should perform."
    )

    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured input passed to the component."
    )


class ConversationAgentContext(BaseModel):
  model_config = ConfigDict(extra="forbid")

  user_request: str
  
  constraints: list[str]
  collected_context: str
  # CHANGE SYSTEM PROMPT WHEN CHANGING
  # ANY FIELD TYPES.  

class OrchestratorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_step: Literal["execute", "respond", "stop"]

    conversation_agent_context: Optional[ConversationAgentContext]

    actions: list[OrchestratorAction] = Field(
        default_factory=list,
        description="Actions for the registry/runtime to execute."
    )

    error: Optional[str] = None