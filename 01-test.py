from agents.conversation_agent import run_conversation_agent

from schemas.conversation_agent import ConversationAgentState

user_input = """
Okay, now lets plan what should be in the
state to the conversation_agent?
"""


state: ConversationAgentState = {
    "user_request": user_input,

    "recent_conversations": [
        {
            "role": "user",
            "content": "I'm working on the Conversation Agent for Jarvis Brain v2."
        },
        {
            "role": "assistant",
            "content": "The Conversation Agent should receive a focused state containing the current request, recent conversation, retrieved context, runtime state, and execution context."
        },
        {
            "role": "user",
            "content": "Now I'm testing the Conversation Agent before the other subsystems are implemented."
        },
    ],

    "relevant_context": {
        "episodic_memory": [
            {
                "id": "ep-test-001",
                "content": "Placeholder episodic memory. The episodic memory subsystem has not been implemented yet.",
                "timestamp": "2026-09-03T21:00:00+05:30",
            }
        ],
        "chat_archives": [
            {
                "id": "chat-test-001",
                "content": "Placeholder chat archive. Chat archive retrieval has not been implemented yet.",
                "timestamp": "2026-09-03T21:00:00+05:30",
            }
        ],
        "learned_knowledge": [
            {
                "id": "knowledge-test-001",
                "content": "Placeholder learned knowledge. Learned-knowledge retrieval has not been implemented yet.",
            }
        ],
    },

    "runtime_state": {
        "task": "Generate a meaningful user-facing response to the current conversation.",
        "input": user_input,
        "steps": [
            {
                "step": "Receive user request",
                "status": "completed",
            },
            {
                "step": "Process request through agentic loop",
                "status": "completed",
            },
            {
                "step": "Prepare context for Conversation Agent",
                "status": "in_progress",
            },
            {
                "step": "Generate final user-facing response",
                "status": "pending",
            },
        ],
        "recent_conversations": [
            {
                "role": "user",
                "content": "I'm working on the Conversation Agent for Jarvis Brain v2."
            },
            {
                "role": "assistant",
                "content": "The Conversation Agent should receive a focused state containing the current request, recent conversation, retrieved context, runtime state, and execution context."
            },
            {
                "role": "user",
                "content": "Now I'm testing the Conversation Agent before the other subsystems are implemented."
            },
        ],
    },

    "execution_context": {
        "actions": [
            {
                "type": "agent",
                "component": "conversation_agent",
                "task": "Generate the final user-facing response.",
                "input": {
                    "source": "agentic_loop",
                },
            }
        ],
        "results": [
            {
                "component": "agentic_loop",
                "status": "success",
                "result": "The request reached the Conversation Agent for final response generation.",
            }
        ],
        "failures": [],
    },
}


res = run_conversation_agent(
  state
)
