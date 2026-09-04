from integrations.base_agent import BaseAgent
from schemas.conversation_agent import ConversationAgentOutput
from schemas.conversation_agent import ConversationAgentState
from schemas.orchestrator_v2 import ConversationAgentHandoff
from schemas.runtime_state import RuntimeState
from configs.settings import CONVERSATION_AGENT_PROMPT_PATH


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


def run_conversation_agent(
    conversation_agent_handoff_state: ConversationAgentHandoff,
    runtime_state: RuntimeState | None = None,
) -> str:
    if runtime_state is None:
        runtime_state = RuntimeState(
            user_request=conversation_agent_handoff_state.user_request,
            objective=conversation_agent_handoff_state.objective,
        )

    state: ConversationAgentState = {
        "user_request": runtime_state.user_request,
        "objective": runtime_state.objective,
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
    }

    response = conversation_agent.invoke(state)

    print(f"\nConversation Agent Response: \n{response.model_dump_json(indent=2)}\n")
  
    if response.error:
        raise ConversationAgentError(response.error)

    if response.response_type == "error":
        raise ConversationAgentError(
            response.response or "Conversation agent returned an error."
        )

    return response.response