from integrations.base_agent import BaseAgent
from schemas.agents.planner import (
    PlannerRelevantContext,
    PlannerResult,
    PlannerState,
)
from configs.settings import PLANNER_PROMPT_PATH


planner_prompt = PLANNER_PROMPT_PATH.read_text(encoding="utf-8")

planner_agent = BaseAgent(
    system_prompt=planner_prompt,
    response_model=PlannerResult,
)


def build_planner_state(
    user_request: str,
    available_components: dict[str, object],
    recent_conversations: list[dict[str, str]] | None = None,
    relevant_context: PlannerRelevantContext | None = None,
    retrieval_errors: list[str] | None = None,
) -> PlannerState:
    return {
        "user_request": user_request,
        "recent_conversations": list(recent_conversations or []),
        "relevant_context": relevant_context or {
            "episodic_memory": [],
            "chat_archives": [],
            "learned_knowledge": [],
        },
        "environment_context": {},
        "available_components": available_components,
        "retrieval_errors": list(retrieval_errors or []),
    }


def run_planner(state: PlannerState) -> PlannerResult:
    response = planner_agent.invoke(state)
    if response.error:
        return response
    return response