from agents.planner import (
  run_planner,
  build_planner_state

)

from configs.mcp_servers import MCP_SERVERS
from packages.MCP import MCPClient

user = "what is the new AI model gpt 6 astra can do?"

with MCPClient(MCP_SERVERS) as mcp_client:
  agent_state = build_planner_state(
    user_request=user,
    available_tools=mcp_client.tools(),
  )

  response = run_planner(agent_state)

print(response)
