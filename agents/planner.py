from integrations.base_agent import BaseAgent
from schemas.planner import PlannerResult, PlannerState
from configs.settings import PLANNER_PROMPT_PATH


planner_prompt = PLANNER_PROMPT_PATH.read_text(encoding="utf-8")

planner_agent = BaseAgent(
    system_prompt=planner_prompt,
    response_model=PlannerResult,
)


def build_planner_state(
    user_request: str,
    available_components: dict[str, object],
) -> PlannerState:
    return {
        "user_request": user_request,
        "recent_conversations": [],
        "relevant_context": {
            "episodic_memory": [],
            "chat_archives": [],
            "learned_knowledge": [],
        },
        "environment_context": {},
        "available_components": available_components,
    }


def run_planner(state: PlannerState) -> PlannerResult:
    response = planner_agent.invoke(state)
    if response.error:
        return response
    return response