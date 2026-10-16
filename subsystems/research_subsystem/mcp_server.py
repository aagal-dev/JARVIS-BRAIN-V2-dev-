"""MCP server adapter for the existing Research Subsystem."""

from typing import Any

from packages.MCP import MCPServer

from .research_workflow import invoke_research_subsystem


server = MCPServer(name="research")


@server.tool(
    name="research",
    description=(
        "Run the Research Subsystem for a query. Returns a structured research "
        "status, synthesis, connector summaries, and any errors."
    ),
)
def research(user_query: str) -> dict[str, Any]:
    result = invoke_research_subsystem(user_query)
    return result.model_dump(mode="json")


if __name__ == "__main__":
    server.run(transport="stdio")
