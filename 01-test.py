from agents.planner import (
  run_planner,
  build_planner_state

)

from core.registry.available_components import AVAILABLE_COMPONENTS

user = "what is the new AI model gpt 6 astra can do?"

agent_state = build_planner_state(
  user_request=user,
  available_components=AVAILABLE_COMPONENTS
)

response = run_planner(agent_state)

print(response)
