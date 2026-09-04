from typing import Any, Callable

from core.orchestrator import run_orchestrator
from core.registry.available_components import AVAILABLE_COMPONENTS
from schemas.jarvis_brain_result import JarvisBrainResult
from schemas.orchestrator_v2 import OrchestratorResult

from agents.conversation_agent import run_conversation_agent

class JarvisBrain:
    def __init__(
        self,
        orchestrator: Callable[
            [dict[str, Any], dict[str, Any]],
            OrchestratorResult,
        ] = run_orchestrator,
        max_steps: int = 5,
    ):
        self.orchestrator = orchestrator
        self.available_components = AVAILABLE_COMPONENTS
        self.runtime_state: dict[str, Any] = {}
        self.max_steps = max_steps
        self.step = 0
        self.workflow_complete = False

    def run(self, user_request: Any = None) -> JarvisBrainResult:
        if not isinstance(user_request, str) or not user_request.strip():
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error="user_request must be a non-empty string.",
                state=self.runtime_state,
            )

        self.step = 0
        self.workflow_complete = False
        self.runtime_state["user_request"] = user_request

        while not self.workflow_complete and self.step < self.max_steps:
            self.step += 1
            self.runtime_state["step"] = self.step

            try:
                decision = self.orchestrator(
                    runtime_state=self.runtime_state,
                    available_components=self.available_components,
                )
              
            except Exception as exc:
                self.workflow_complete = True
                return JarvisBrainResult(
                    status="failed",
                    error=f"Orchestrator failure: {str(exc)[:2000]}",
                    state=self.runtime_state,
                )

            print(f"\nORCHESTRATOR DECISION: \n{decision.model_dump_json(indent=2)}\n")
        
            # EDGE CASES & EXCEPTIONS
            if not isinstance(decision, OrchestratorResult):
                self.workflow_complete = True
                return JarvisBrainResult(
                    status="failed",
                    error="Orchestrator returned an unexpected response type.",
                    state=self.runtime_state,
                )


            if decision.error:
                self.workflow_complete = True
                return JarvisBrainResult(
                    status="failed",
                    error=result.error,
                    state=self.runtime_state,
                )

            # runtime update
            self.runtime_state["orchestrator_result"] = decision.model_dump()

            if decision.next_step == "respond":
                print("\n[JARVIS BRAIN] CONVERSATION AGENT")
                print("Context:", decision.conversation_agent_handoff)
 
                conversation_agent_response = run_conversation_agent(decision.conversation_agent_handoff)

                self.workflow_complete = True
                return JarvisBrainResult(
                    status="success",
                    output=conversation_agent_response,
                    state=self.runtime_state,
                )

            if decision.next_step == "execute":
                if not decision.actions:
                    self.workflow_complete = True
                    return JarvisBrainResult(
                        status="failed",
                        error="Orchestrator requested execution but returned no actions.",
                        state=self.runtime_state,
                    )

                for action in decision.actions:
                    print(
                        f"\n[JARVIS BRAIN] ACTION"
                        f"\nType: {action.type}"
                        f"\nComponent: {action.component}"
                        f"\nProvided Goal: {action.input.goal}"
                    )

                self.runtime_state["last_actions"] = [
                    action.model_dump() for action in decision.actions
                ]

        self.workflow_complete = True

        return JarvisBrainResult(
            status="partial",
            output=self.runtime_state.get("orchestrator_result"),
            error="Maximum workflow steps reached before completion.",
            state=self.runtime_state,
        )