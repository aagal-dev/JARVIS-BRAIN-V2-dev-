from integrations.base_agent import BaseAgent
from schemas.orchestrator_v2 import OrchestratorResult
from configs.settings import ORCHESTRATOR_PROMPT_PATH

# Prompt 
orchestrator_prompt = ORCHESTRATOR_PROMPT_PATH.read_text(encoding="utf-8")

# Agent creation 
orchestrator = BaseAgent(
  system_prompt=orchestrator_prompt,
  response_model=OrchestratorResult
)


def run_orchestrator(runtime_state: dict, available_components: dict) -> OrchestratorResult:

  state = {
    "runtime_state": runtime_state,
    "available_components": available_components
  }
  
  response = orchestrator.invoke(state)

  if response.error:
    raise TypeError(f"Orchestrator execution failed: {response.error}")
    
  return response