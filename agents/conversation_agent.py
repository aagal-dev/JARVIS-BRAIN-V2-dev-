from integrations.base_agent import BaseAgent
from schemas.agents.conversation_agent import (
    ConversationAgentOutput,
    ConversationAgentState,
)
from schemas.orchestrator.orchestrator_v2 import ConversationAgentHandoff
from schemas.system.runtime_state import RuntimeState
from configs.settings import CONVERSATION_AGENT_PROMPT_PATH

from threaded_services.registered_services import service_state_store

class ConversationAgentError(RuntimeError):
    """Raised when the conversation agent fails to execute."""


# Prompt
conversation_agent_prompt = CONVERSATION_AGENT_PROMPT_PATH.read_text(
    encoding="utf-8"
)

# Agent creation
conversation_agent = BaseAgent(
    system_prompt=conversation_agent_prompt,
    response_model=ConversationAgentOutput,
)


def build_conversation_agent_state(
    conversation_agent_handoff_state: ConversationAgentHandoff,
    runtime_state: RuntimeState,
) -> ConversationAgentState:

    snapshot = service_state_store.snapshot()["time"]

    service_state = snapshot.model_dump()
  
    return {
        "user_request": conversation_agent_handoff_state.user_request,
        "next_suggested_action": conversation_agent_handoff_state.objective,
        "recent_conversations": [],
        "relevant_context": {
            "episodic_memory": [],
            "chat_archives": [],
            "learned_knowledge": [],
        },
        "runtime_state": runtime_state,
        "execution_context": {
            "actions": [],
            "results": [],
            "failures": [],
        },
        "environmemt": {
          "time_and_celender": service_state
        }
    }


def run_conversation_agent(
    state: ConversationAgentState,
) -> ConversationAgentOutput:
    response = conversation_agent.invoke(state)

    print(
        f"\nConversation Agent Response: "
        f"\n{response.model_dump_json(indent=2)}\n"
    )

    if response.error:
        raise ConversationAgentError(response.error)

    if response.response_type == "error":
        raise ConversationAgentError(
            response.response or "Conversation agent returned an error."
        )

    return response