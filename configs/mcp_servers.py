"""Central configuration for internal and external MCP servers."""

import sys
from pathlib import Path

from packages.MCP import MCPServerConfig, StdioTransport


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Add more MCPServerConfig entries here. Each can use any transport supported
# by the customized MCP SDK, including StdioTransport and StreamableHTTPTransport.
MCP_SERVERS: tuple[MCPServerConfig, ...] = (
    MCPServerConfig(
        name="research",
        transport=StdioTransport(
            command=sys.executable,
            args=("-m", "subsystems.research_subsystem.mcp_server"),
            cwd=str(PROJECT_ROOT),
        ),
        timeout=600.0
    ),
)
