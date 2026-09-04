from typing import Any, Callable

from core.orchestrator import run_orchestrator
from core.registry.available_components import AVAILABLE_COMPONENTS
from core.runtime_state_manager import RuntimeStateManager
from schemas.jarvis_brain_result import JarvisBrainResult
from schemas.orchestrator_v2 import ConversationAgentHandoff, OrchestratorResult
from schemas.runtime_state import RuntimeState

from agents.conversation_agent import run_conversation_agent


class JarvisBrain:
    def __init__(
        self,
        orchestrator: Callable[
            [RuntimeState | dict[str, Any], dict[str, Any]],
            OrchestratorResult,
        ] = run_orchestrator,
        max_steps: int = 5,
        runtime_state_manager: RuntimeStateManager | None = None,
        conversation_agent: Callable[
            [ConversationAgentHandoff, RuntimeState], str
        ] = run_conversation_agent,
    ):
        self.orchestrator = orchestrator
        self.available_components = AVAILABLE_COMPONENTS
        self.runtime_state_manager = runtime_state_manager or RuntimeStateManager()
        self.conversation_agent = conversation_agent
        self._execution_state: dict[str, Any] = {}
        self.max_steps = max_steps
        self.step = 0
        self.workflow_complete = False

    @property
    def runtime_state(self) -> RuntimeState:
        return self.runtime_state_manager.get()

    def run(self, user_request: Any = None) -> JarvisBrainResult:
        if not isinstance(user_request, str) or not user_request.strip():
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error="user_request must be a non-empty string.",
                state={},
            )

        runtime_state = self.runtime_state_manager.create(user_request=user_request)
        self._execution_state = {}
        self.step = 0
        self.workflow_complete = False

        while not self.workflow_complete and self.step < self.max_steps:
            self.step += 1
            self._execution_state["orchestration_step"] = self.step

            try:
                decision = self.orchestrator(
                    runtime_state=runtime_state.model_dump(),
                    available_components=self.available_components,
                )
              
            except Exception as exc:
                self.workflow_complete = True
                return JarvisBrainResult(
                    status="failed",
                    error=f"Orchestrator failure: {str(exc)[:2000]}",
                    state=runtime_state.model_dump(),
                )

            print(f"\nORCHESTRATOR DECISION: \n{decision.model_dump_json(indent=2)}\n")
        
            # EDGE CASES & EXCEPTIONS
            if not isinstance(decision, OrchestratorResult):
                self.workflow_complete = True
                return JarvisBrainResult(
                    status="failed",
                    error="Orchestrator returned an unexpected response type.",
                    state=runtime_state.model_dump(),
                )


            if decision.error:
                self.workflow_complete = True
                return JarvisBrainResult(
                    status="failed",
                    error=decision.error,
                    state=runtime_state.model_dump(),
                )

            self._execution_state["orchestrator_result"] = decision.model_dump()

            if decision.next_step == "respond":
                print("\n[JARVIS BRAIN] CONVERSATION AGENT")
                print("Context:", decision.conversation_agent_handoff)

                conversation_agent_response = self.conversation_agent(
                    decision.conversation_agent_handoff,
                    runtime_state,
                )

                self.workflow_complete = True
                runtime_state = self.runtime_state_manager.complete()
                return JarvisBrainResult(
                    status="success",
                    output=conversation_agent_response,
                    state=runtime_state.model_dump(),
                )

            if decision.next_step == "execute":
                if not decision.actions:
                    self.workflow_complete = True
                    return JarvisBrainResult(
                        status="failed",
                        error="Orchestrator requested execution but returned no actions.",
                        state=runtime_state.model_dump(),
                    )

                for action in decision.actions:
                    print(
                        f"\n[JARVIS BRAIN] ACTION"
                        f"\nType: {action.type}"
                        f"\nComponent: {action.component}"
                        f"\nProvided Goal: {action.input.goal}"
                    )

                self._execution_state["last_actions"] = [
                    action.model_dump() for action in decision.actions
                ]

        self.workflow_complete = True

        return JarvisBrainResult(
            status="partial",
            output=self._execution_state.get("orchestrator_result"),
            error="Maximum workflow steps reached before completion.",
            state=runtime_state.model_dump(),
        )