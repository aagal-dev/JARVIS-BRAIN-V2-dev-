from typing import Any, Callable

from agents.conversation_agent import (
    build_conversation_agent_state,
    run_conversation_agent,
)
from agents.planner import build_planner_state, run_planner
from core.orchestrator import run_orchestrator
from core.registry.available_components import AVAILABLE_COMPONENTS
from core.runtime_state_manager import RuntimeStateManager
from schemas.conversation_agent import ConversationAgentState
from schemas.jarvis_brain_result import JarvisBrainResult
from schemas.orchestrator_v2 import OrchestratorResult
from schemas.planner import PlannerResult, PlannerState
from schemas.runtime_state import RuntimeState, RuntimeStep


class JarvisBrain:
    def __init__(
        self,
        orchestrator: Callable[
            [RuntimeState | dict[str, Any], dict[str, Any]],
            OrchestratorResult,
        ] = run_orchestrator,
        max_steps: int = 5,
        runtime_state_manager: RuntimeStateManager | None = None,
        conversation_agent: Callable[[ConversationAgentState], str] = run_conversation_agent,
        planner: Callable[[PlannerState], PlannerResult] = run_planner,
    ):
        self.orchestrator = orchestrator
        self.available_components = AVAILABLE_COMPONENTS
        self.runtime_state_manager = runtime_state_manager or RuntimeStateManager()
        self.conversation_agent = conversation_agent
        self.planner = planner
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

        planner_state = build_planner_state(
            user_request=user_request,
            available_components=self.available_components,
        )

        try:
            plan = self.planner(planner_state)
        except Exception as exc:
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error=f"Planner failure: {str(exc)[:2000]}",
                state={},
            )

        if not isinstance(plan, PlannerResult):
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error="Planner returned an unexpected response type.",
                state={},
            )

        if plan.error:
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error=plan.error,
                state={},
            )

        if not plan.objective.strip():
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error="Planner returned an empty objective.",
                state={},
            )

        try:
            runtime_state = self.runtime_state_manager.create(
                user_request=user_request,
                objective=plan.objective,
                steps=[
                    RuntimeStep(
                        id=step.id,
                        step=step.step,
                        status=step.status,
                    )
                    for step in plan.steps
                ],
            )
        except Exception as exc:
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error=f"Runtime State initialization failed: {str(exc)[:2000]}",
                state={},
            )

        self.step = 0
        self.workflow_complete = False
        last_decision: OrchestratorResult | None = None

        while not self.workflow_complete and self.step < self.max_steps:
            self.step += 1

            print(f"\nRUNTIME STATE: \n{runtime_state.model_dump_json(indent=2)}")
            
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

            last_decision = decision

            if decision.next_step == "respond":
                print("\n[JARVIS BRAIN] CONVERSATION AGENT")
                print("Context:", decision.conversation_agent_handoff)

                conversation_agent_state = build_conversation_agent_state(
                    conversation_agent_handoff_state=decision.conversation_agent_handoff,
                    runtime_state=runtime_state,
                )
                conversation_agent_response = self.conversation_agent(
                    conversation_agent_state,
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

        self.workflow_complete = True

        return JarvisBrainResult(
            status="partial",
            output=last_decision.model_dump() if last_decision else None,
            error="Maximum workflow steps reached before completion.",
            state=runtime_state.model_dump(),
        )