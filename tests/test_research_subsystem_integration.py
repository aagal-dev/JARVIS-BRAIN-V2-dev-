from __future__ import annotations

from typing import Any

from core.agentic_loop import JarvisBrain
from subsystems.research_subsystem.research_workflow import (
    invoke_research_subsystem,
)
from subsystems.research_subsystem.types import ResearchResult
from schemas.agents.conversation_agent import ConversationAgentOutput
from schemas.agents.planner_v2 import PlannerResult
from schemas.orchestrator.orchestrator_v2 import (
    ConversationAgentHandoff,
    OrchestratorResult,
)


class StubConnector:
    name = "stub"

    def execute(self, query: str) -> dict[str, Any]:
        return {
            "connector": self.name,
            "query": query,
            "results": [
                {
                    "title": "A grounded source",
                    "url": "https://example.test/source",
                    "text": (
                        "This is sufficiently long grounded evidence for the "
                        "cleaner and summarizer test path."
                    ),
                }
            ],
        }


class StubRegistry:
    def get_many(self, names: list[str]) -> list[StubConnector]:
        assert names == ["stub"]
        return [StubConnector()]


class StubSummarizer:
    def run(self, results: Any) -> str:
        assert len(results) == 1
        return "Compressed grounded evidence."


def test_research_pipeline_returns_typed_result_without_raw_connector_payloads() -> None:
    result = invoke_research_subsystem(
        "Explain the test topic",
        planner=lambda query: {"main_goal": query},
        executor=lambda plan: {
            "sq_1": {
                "executions": [
                    {"query": "focused test topic", "connectors": ["stub"]}
                ]
            }
        },
        registry=StubRegistry(),
        summarizer_factory=StubSummarizer,
        synthesizer=lambda connector_results, query: {
            "overview": connector_results,
            "key_findings": ["The test path completed."],
        },
    )

    assert isinstance(result, ResearchResult)
    assert result.status == "success"
    assert result.synthesis == {
        "overview": "Compressed grounded evidence.",
        "key_findings": ["The test path completed."],
    }
    assert result.connector_executions[0].connector == "stub"
    assert result.connector_executions[0].result_count == 1
    assert "results" not in result.model_dump()


def test_brain_executes_research_and_hands_structured_result_to_conversation() -> None:
    observed_conversation_state: dict[str, Any] = {}
    observed_orchestrator_states: list[dict[str, Any]] = []
    orchestrator_calls = 0
    research_result = ResearchResult(
        status="success",
        query="Research the test topic",
        synthesis={"key_findings": ["The finding is grounded."]},
    )

    def fake_planner(state: dict[str, Any]) -> PlannerResult:
        return PlannerResult(
            mode="planned",
            objective="Research the test topic",
            steps=[
                {
                    "id": "step-1",
                    "step": "Research the topic",
                    "status": "pending",
                }
            ],
        )

    def fake_orchestrator(runtime_state, available_components):
        nonlocal orchestrator_calls
        orchestrator_calls += 1
        observed_orchestrator_states.append(runtime_state)
        if orchestrator_calls == 1:
            return OrchestratorResult(
                next_step="execute",
                actions=[
                    {
                        "type": "subsystem",
                        "component": "research_subsystem",
                        "input": {
                            "user_request": "Research the test topic",
                            "goal": "Research the test topic",
                        },
                    }
                ],
            )
        return OrchestratorResult(
            next_step="respond",
            conversation_agent_handoff=ConversationAgentHandoff(
                user_request="Research the test topic",
                objective="Explain the research finding.",
            ),
        )

    def fake_conversation_agent(state):
        observed_conversation_state.update(state)
        return ConversationAgentOutput(
            response="The finding is grounded.",
            response_type="answer",
        )

    brain = JarvisBrain(
        orchestrator=fake_orchestrator,
        planner=fake_planner,
        conversation_agent=fake_conversation_agent,
        research_subsystem=lambda query: research_result,
    )

    result = brain.run("Research the test topic")

    assert result.status == "success"
    assert result.state["steps"][0]["status"] == "completed"
    assert result.state["steps"][0]["result"] == research_result.model_dump(
        mode="json"
    )
    assert observed_conversation_state["execution_context"]["results"] == [
        research_result.model_dump(mode="json")
    ]
    assert observed_orchestrator_states[1]["steps"][0]["result"] == (
        research_result.model_dump(mode="json")
    )
    assert orchestrator_calls == 2


def test_brain_attaches_research_result_for_direct_mode_execution() -> None:
    research_result = ResearchResult(
        status="success",
        query="Look up the direct topic",
        synthesis="Direct-mode synthesis.",
    )
    orchestrator_calls = 0

    def fake_orchestrator(runtime_state, available_components):
        nonlocal orchestrator_calls
        orchestrator_calls += 1
        if orchestrator_calls == 1:
            return OrchestratorResult(
                next_step="execute",
                actions=[
                    {
                        "type": "subsystem",
                        "component": "research_subsystem",
                        "input": {
                            "user_request": "Look up the direct topic",
                            "goal": "Look up the direct topic",
                        },
                    }
                ],
            )
        return OrchestratorResult(
            next_step="respond",
            conversation_agent_handoff=ConversationAgentHandoff(
                user_request="Look up the direct topic",
                objective="Share the research result.",
            ),
        )

    brain = JarvisBrain(
        orchestrator=fake_orchestrator,
        planner=lambda state: PlannerResult(mode="direct"),
        conversation_agent=lambda state: ConversationAgentOutput(
            response="Direct result.",
            response_type="answer",
        ),
        research_subsystem=lambda query: research_result,
    )

    result = brain.run("Look up the direct topic")

    assert result.status == "success"
    assert result.state["steps"][0]["id"] == "execution-1-1"
    assert result.state["steps"][0]["result"] == research_result.model_dump(
        mode="json"
    )
