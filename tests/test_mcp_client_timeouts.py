import asyncio
from types import SimpleNamespace

import pytest

from packages.MCP import MCPClient, MCPServerConfig, StdioTransport


class RecordingRuntime:
    def call(self, coroutine, timeout):
        self.timeout = timeout
        return asyncio.run(coroutine)


class RecordingSession:
    async def call_tool(self, _tool, _arguments, *, read_timeout_seconds):
        self.read_timeout_seconds = read_timeout_seconds
        return SimpleNamespace(content=[], isError=False)


@pytest.mark.parametrize(
    ("client_timeout", "expected_timeout"),
    [(None, 600.0), (5.0, 5.0)],
)
def test_call_tool_uses_the_effective_timeout_for_client_and_session(
    client_timeout,
    expected_timeout,
) -> None:
    config = MCPServerConfig(
        name="research",
        transport=StdioTransport(command="python"),
        timeout=600.0,
    )
    client = MCPClient((config,), timeout=client_timeout)
    runtime = RecordingRuntime()
    session = RecordingSession()
    client._runtime = runtime
    client._sessions["research"] = session
    client._connected = True

    client.call_tool("research__research", {"user_query": "query"})

    assert runtime.timeout == expected_timeout
    assert session.read_timeout_seconds == expected_timeout
