"""Small stdio MCP server used by integration tests."""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.MCP import MCPServer


def main() -> None:
    label = sys.argv[1]
    server = MCPServer(name=label)

    @server.tool(name="echo", description="Return the label and supplied value.")
    def echo(value: str) -> dict[str, Any]:
        return {"server": label, "value": value}

    @server.tool(name="fail", description="Raise a predictable tool error.")
    def fail(message: str) -> str:
        raise ValueError(message)

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
