import pytest
from pydantic import ValidationError

from schemas.orchestrator.orchestrator_v2 import (
    ConversationAgentHandoff,
    OrchestratorNextStep,
    OrchestratorResult,
)


def test_nested_respond_transition_is_normalized_to_flat_result() -> None:
    result = OrchestratorResult.model_validate(
        {
            "next_step": {
                "type": "respond",
                "actions": [],
                "conversation_agent_handoff": {
                    "user_request": "What is this?",
                    "objective": "Explain the referenced item.",
                },
            }
        }
    )

    assert result.next_step is OrchestratorNextStep.RESPOND
    assert result.actions == []
    assert result.conversation_agent_handoff == ConversationAgentHandoff(
        user_request="What is this?",
        objective="Explain the referenced item.",
    )


def test_nested_execute_transition_is_normalized_to_flat_result() -> None:
    result = OrchestratorResult.model_validate(
        {
            "next_step": {
                "type": "execute",
                "actions": [
                    {
                        "tool_name": "research__research",
                        "arguments": {"user_query": "Find relevant sources"},
                    }
                ],
            }
        }
    )

    assert result.next_step is OrchestratorNextStep.EXECUTE
    assert result.actions[0].tool_name == "research__research"
    assert result.conversation_agent_handoff is None


def test_conflicting_nested_and_top_level_transition_data_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Conflicting 'actions' values"):
        OrchestratorResult.model_validate(
            {
                "next_step": {
                    "type": "execute",
                    "actions": [
                        {
                            "tool_name": "research__research",
                            "arguments": {},
                        }
                    ],
                },
                "actions": [],
            }
        )
