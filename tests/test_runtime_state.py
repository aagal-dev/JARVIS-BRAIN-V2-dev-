import unittest
from unittest.mock import patch

from pydantic import ValidationError

from agents.conversation_agent import (
    build_conversation_agent_state,
    run_conversation_agent,
)
from core.agentic_loop import JarvisBrain
from core.orchestrator import run_orchestrator
from core.runtime_state_manager import (
    RuntimeStateManager,
    RuntimeStateNotInitializedError,
)
from schemas.orchestrator_v2 import ConversationAgentHandoff, OrchestratorResult
from schemas.runtime_state import RuntimeState, RuntimeStep


class RuntimeStateModelTests(unittest.TestCase):
    def test_locked_runtime_state_shape(self) -> None:
        state = RuntimeState(
            user_request="Organize my notes",
            objective="Organize my notes",
            steps=[RuntimeStep(id="step-001", step="Collect notes")],
        )

        self.assertEqual(
            state.model_dump(),
            {
                "user_request": "Organize my notes",
                "objective": "Organize my notes",
                "steps": [
                    {
                        "id": "step-001",
                        "step": "Collect notes",
                        "result": None,
                        "status": "pending",
                    }
                ],
                "current_step_id": None,
            },
        )

    def test_runtime_state_rejects_unlocked_fields(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeState(
                user_request="Request",
                objective="Objective",
                result="not allowed",
            )

    def test_runtime_state_rejects_duplicate_or_unknown_step_references(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeState(
                user_request="Request",
                objective="Objective",
                steps=[
                    RuntimeStep(id="step-001", step="First"),
                    RuntimeStep(id="step-001", step="Duplicate"),
                ],
            )

        with self.assertRaises(ValidationError):
            RuntimeState(
                user_request="Request",
                objective="Objective",
                current_step_id="missing",
            )


class RuntimeStateManagerTests(unittest.TestCase):
    def test_manager_lifecycle_and_step_progression(self) -> None:
        manager = RuntimeStateManager()
        with self.assertRaises(RuntimeStateNotInitializedError):
            manager.get()

        created = manager.create(
            user_request="Complete a two-step task",
            steps=[
                RuntimeStep(id="step-001", step="First step"),
                RuntimeStep(id="step-002", step="Second step"),
            ],
        )
        self.assertEqual(created.objective, created.user_request)
        self.assertIsNone(created.current_step_id)

        active = manager.set_current_step("step-001")
        self.assertEqual(active.current_step_id, "step-001")
        self.assertEqual(active.steps[0].status, "in_progress")

        with_result = manager.update_step_result(
            "step-001",
            "Collected three notes.",
        )
        self.assertEqual(with_result.steps[0].result, "Collected three notes.")

        completed = manager.update_step_status("step-001", "completed")
        self.assertIsNone(completed.current_step_id)
        self.assertEqual(completed.steps[0].status, "completed")
        self.assertEqual(completed.steps[0].result, "Collected three notes.")

        active = manager.set_current_step("step-002")
        self.assertEqual(active.current_step_id, "step-002")
        self.assertEqual(active.steps[1].status, "in_progress")

        final = manager.complete()
        self.assertTrue(manager.is_complete)
        self.assertIsNone(final.current_step_id)
        self.assertEqual(final.steps[1].status, "completed")

    def test_get_returns_a_defensive_copy(self) -> None:
        manager = RuntimeStateManager()
        manager.create("Request")

        state = manager.get()
        state.objective = "Changed outside manager"

        self.assertEqual(manager.get().objective, "Request")


class BrainRuntimeIntegrationTests(unittest.TestCase):
    def test_orchestrator_receives_step_results_in_runtime_state(self) -> None:
        captured_state = {}

        class StubOrchestrator:
            def invoke(self, state):
                captured_state.update(state)
                return OrchestratorResult(
                    next_step="stop",
                )

        runtime_state = RuntimeState(
            user_request="Research the topic",
            objective="Research the topic",
            steps=[
                RuntimeStep(
                    id="step-001",
                    step="Gather sources",
                    status="completed",
                    result="Found two relevant sources.",
                )
            ],
        )

        with patch("core.orchestrator.orchestrator", StubOrchestrator()):
            run_orchestrator(runtime_state, available_components={})

        self.assertEqual(
            captured_state["runtime_state"]["steps"][0]["result"],
            "Found two relevant sources.",
        )

    def test_conversation_agent_receives_locked_runtime_state(self) -> None:
        captured_state = {}

        class StubConversationAgent:
            def invoke(self, state):
                captured_state.update(state)
                from schemas.conversation_agent import ConversationAgentOutput

                return ConversationAgentOutput(
                    response="stub response",
                    response_type="answer",
                )

        runtime_state = RuntimeState(
            user_request="Summarize this",
            objective="Summarize this clearly",
            steps=[
                RuntimeStep(
                    id="step-001",
                    step="Summarize",
                    result="The source contains three key points.",
                )
            ],
        )
        handoff = ConversationAgentHandoff(
            user_request=runtime_state.user_request,
            objective=runtime_state.objective,
        )

        state = build_conversation_agent_state(handoff, runtime_state)

        with patch(
            "agents.conversation_agent.conversation_agent",
            StubConversationAgent(),
        ):
            response = run_conversation_agent(state)

        self.assertEqual(response, "stub response")
        self.assertIs(captured_state["runtime_state"], runtime_state)
        self.assertEqual(captured_state["objective"], "Summarize this clearly")
        self.assertEqual(
            captured_state["runtime_state"].steps[0].result,
            "The source contains three key points.",
        )

    def test_runtime_state_is_created_and_fused_into_workflow(self) -> None:
        observed_runtime_states: list[dict] = []
        observed_handoffs: list[tuple[str, str]] = []

        def fake_orchestrator(runtime_state, available_components):
            observed_runtime_states.append(runtime_state)
            return OrchestratorResult(
                next_step="respond",
                conversation_agent_handoff=ConversationAgentHandoff(
                    user_request=runtime_state["user_request"],
                    objective=runtime_state["objective"],
                ),
            )

        def fake_conversation_agent(state):
            runtime_state = state["runtime_state"]
            observed_handoffs.append(
                (state["user_request"], runtime_state.user_request)
            )
            return "Runtime-aware response"

        brain = JarvisBrain(
            orchestrator=fake_orchestrator,
            conversation_agent=fake_conversation_agent,
        )
        result = brain.run("Explain the runtime state")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.output, "Runtime-aware response")
        self.assertEqual(
            result.state,
            {
                "user_request": "Explain the runtime state",
                "objective": "Explain the runtime state",
                "steps": [],
                "current_step_id": None,
            },
        )
        self.assertEqual(
            observed_runtime_states,
            [
                {
                    "user_request": "Explain the runtime state",
                    "objective": "Explain the runtime state",
                    "steps": [],
                    "current_step_id": None,
                }
            ],
        )
        self.assertEqual(
            observed_handoffs,
            [("Explain the runtime state", "Explain the runtime state")],
        )
        self.assertTrue(brain.runtime_state_manager.is_complete)

    def test_orchestrator_error_is_returned_without_name_error(self) -> None:
        def failing_orchestrator(runtime_state, available_components):
            return OrchestratorResult(
                next_step="stop",
                error="Orchestrator unavailable",
            )

        brain = JarvisBrain(orchestrator=failing_orchestrator)
        result = brain.run("Try the workflow")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "Orchestrator unavailable")


if __name__ == "__main__":
    unittest.main()