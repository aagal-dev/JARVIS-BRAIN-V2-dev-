from collections.abc import Callable, Sequence
from typing import Any

from agents.conversation_agent import (
    build_conversation_agent_state,
    run_conversation_agent,
)
from agents.planner import build_planner_state, run_planner
from core.orchestrator import run_orchestrator
from core.runtime_state_manager import RuntimeStateManager
from configs.mcp_servers import MCP_SERVERS
from packages.MCP import MCPClient, MCPServerConfig
from memory.episodic.service import (
    EpisodicConsolidationResult,
    EpisodicMemoryService,
)
from memory.retrieval import MemoryRetrieval
from schemas.agents.conversation_agent import ConversationAgentOutput
from schemas.episodic_memory import ChatHistoryMessage
from schemas.agents.conversation_agent import ConversationAgentState
from schemas.memory_retrieval import MemoryRetrievalResult
from schemas.system.jarvis_brain_result import JarvisBrainResult
from schemas.orchestrator.orchestrator_v2 import OrchestratorResult
from schemas.agents.planner_v2 import PlannerResult, PlannerState
from schemas.system.runtime_state import RuntimeState, RuntimeStep

from threaded_services.registered_services import service_manager

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
            [ConversationAgentState], ConversationAgentOutput
        ] = run_conversation_agent,
        planner: Callable[[PlannerState], PlannerResult] = run_planner,
        episodic_memory: EpisodicMemoryService | None = None,
        memory_retrieval: MemoryRetrieval | None = None,
        mcp_servers: Sequence[MCPServerConfig] | None = None,
    ):
        self.orchestrator = orchestrator
        self.mcp_servers = tuple(MCP_SERVERS if mcp_servers is None else mcp_servers)
        self.runtime_state_manager = runtime_state_manager or RuntimeStateManager()
        self.conversation_agent = conversation_agent
        self.planner = planner
        self.episodic_memory = episodic_memory or EpisodicMemoryService(
            retrieval=memory_retrieval,
        )
        if memory_retrieval is not None:
            self.episodic_memory.retrieval = memory_retrieval
        self.memory_retrieval = (
            memory_retrieval or self.episodic_memory.retrieval
        )
        self.last_memory_retrieval: MemoryRetrievalResult | None = None
        self.chat_history: list[ChatHistoryMessage] = []
        self.max_steps = max_steps
        self.step = 0
        self.workflow_complete = False

    @property
    def runtime_state(self) -> RuntimeState:
        return self.runtime_state_manager.get()

    # MAIN ENTRY POINT
    def run(self, user_request: Any = None) -> JarvisBrainResult:
        mcp_client: MCPClient | None = None
        try:
          # starting all threaded services
          service_manager.start_all()
          
          if not isinstance(user_request, str) or not user_request.strip():
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error="user_request must be a non-empty string.",
                state={},
            )

          mcp_client = MCPClient(self.mcp_servers)
          try:
            mcp_client.connect()
            available_tools = mcp_client.tools()
          except Exception as exc:
            self.workflow_complete = True
            return JarvisBrainResult(
                status="failed",
                error=f"MCP connection or discovery failed: {str(exc)[:2000]}",
                state={},
            )

          self.chat_history.append(
              {
                  "role": "user",
                  "content": user_request,
              }
          )

          try:
            # Retrieving relavent context
            self.last_memory_retrieval = self.memory_retrieval.retrieve(
                user_request
            )

            print(self.last_memory_retrieval)
          except Exception as exc:
            self.last_memory_retrieval = MemoryRetrievalResult(
                query=user_request,
                error=f"Memory retrieval failed: {str(exc)[:2000]}",
            )

          retrieved_context = {
            "episodic_memory": self.last_memory_retrieval.as_context(),
            "chat_archives": [],
            "learned_knowledge": [],
          }

          print(f"\nRetrieved Context: \n{retrieved_context}")

          planner_state = build_planner_state(
             user_request=user_request,
              available_tools=available_tools,
              recent_conversations=self.chat_history[:-1],
              relevant_context=retrieved_context,
              retrieval_errors=(
                  [self.last_memory_retrieval.error]
                  if self.last_memory_retrieval.error
                  else []
              ),
          )

          try:
             plan = self.planner(planner_state)

             print(f"\nPLANNER RESPONSE:\n{plan.model_dump_json(indent=2)}")
          except Exception as exc:
             self.workflow_complete = True
             return JarvisBrainResult(
                 status="failed",
                 error=f"Planner failure: {str(exc)[:2000]}",
                 state={},
             )

             #return plan
          
          # Planner exceptions
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

          if plan.mode not in {"direct", "planned"}:
            self.workflow_complete = True
            return JarvisBrainResult(
              status="failed",
              error=f"Planner returned invalid mode: {plan.mode}",
              state={},
            )
            
          # when the direct response
          if plan.mode == "direct":

            try:
              # runtime with only user_request
              runtime_state = self.runtime_state_manager.create(
                  user_request=user_request
              )
            except Exception as exc:
              self.workflow_complete = True
              return JarvisBrainResult(
                  status="failed",
                  error=f"Runtime State initialization failed: {str(exc)[:2000]}",
                  state={},
              )

            print("\nruntime state updated with user_request only")

          # when multi-step iteration needed
          if plan.mode == "planned":
            if not plan.objective.strip():
               self.workflow_complete = True
               return JarvisBrainResult(
                  status="failed",
                  error="Planner returned an empty objective.",
                  state={},
               )
          
            print(f"\nPLAN PROPOSED:\n{plan}")

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

            print("\nruntime state updated with user_request, plan")


          self.step = 0
          self.workflow_complete = False
          last_decision: OrchestratorResult | None = None

          while not self.workflow_complete and self.step < self.max_steps:
            self.step += 1

            # UPDATING CURRENT STEP AND STATUS
            runtime_state = self.runtime_state_manager.get()

            if runtime_state.current_step_id is None:
              pending_step = next((
                step
                for step in runtime_state.steps
                if step.status == "pending"
              ),
              None,
            )

            if pending_step is not None:
              runtime_state = self.runtime_state_manager.set_current_step(
                pending_step.id
            )

            print(f"\nRUNTIME STATE: \n{runtime_state.model_dump_json(indent=2)}")
            
            try:
              decision = self.orchestrator(
                runtime_state=runtime_state.model_dump(),
                available_tools=available_tools,
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
                  recent_conversations=self.chat_history[:-1],
                  relevant_context=retrieved_context,
                )
                conversation_agent_response = self.conversation_agent(
                  conversation_agent_state,
                )
  
                self.workflow_complete = True
                runtime_state = self.runtime_state_manager.complete()

                self.chat_history.append(
                    {
                        "role": "assistant",
                        "content": conversation_agent_response.response or "",
                    }
                )

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
  
                for action_index, action in enumerate(decision.actions):
                    runtime_state = self.runtime_state_manager.get()
                    step_id = runtime_state.current_step_id

                    if step_id is None:
                        pending_step = next(
                            (
                                step
                                for step in runtime_state.steps
                                if step.status == "pending"
                            ),
                            None,
                        )
                        if pending_step is not None:
                            step_id = pending_step.id
                            runtime_state = (
                                self.runtime_state_manager.set_current_step(step_id)
                            )
                        else:
                            step_id = f"execution-{self.step}-{action_index + 1}"
                            runtime_state = self.runtime_state_manager.add_step(
                                RuntimeStep(
                                    id=step_id,
                                    step=f"Execute {action.tool_name}",
                                )
                            )
                            runtime_state = (
                                self.runtime_state_manager.set_current_step(step_id)
                            )

                    print(
                        f"\n[JARVIS BRAIN] ACTION"
                        f"\nMCP tool: {action.tool_name}"
                    )

                    try:
                        tool_result = mcp_client.call_tool(
                            action.tool_name,
                            action.arguments,
                        )
                        result_payload = {
                            "tool_name": action.tool_name,
                            **tool_result.agent_view(),
                        }
                        print(f"\nMCP Tool Result: \n{result_payload}")
                      
                    except Exception as exc:
                        result_payload = {
                            "tool_name": action.tool_name,
                            "ok": False,
                            "error": f"MCP tool execution failed: {str(exc)[:2000]}",
                        }

                    self.runtime_state_manager.update_step_result(
                        step_id,
                        result_payload,
                    )
                    self.runtime_state_manager.update_step_status(
                        step_id,
                        "completed",
                    )
                    runtime_state = self.runtime_state_manager.get()
  
          self.workflow_complete = True
  
          return JarvisBrainResult(
              status="partial",
              output=last_decision.model_dump() if last_decision else None,
              error="Maximum workflow steps reached before completion.",
              state=runtime_state.model_dump(),
          )

        finally:
          try:
            if mcp_client is not None:
              mcp_client.close()
          finally:
            # stopping all threaded services
            service_manager.stop_all()

    def end_session(self) -> EpisodicConsolidationResult:
        """Consolidate the temporary chat history once the session ends."""
        result = self.episodic_memory.consolidate(self.chat_history)
        if result.error is None:
            self.chat_history.clear()
        return result
