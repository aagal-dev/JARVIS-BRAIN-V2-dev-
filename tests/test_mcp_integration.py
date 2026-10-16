from __future__ import annotations

import sys
from pathlib import Path

import pytest

from configs.mcp_servers import MCP_SERVERS, PROJECT_ROOT
from core.agentic_loop import JarvisBrain
from packages.MCP import (
    MCPClient,
    MCPConnectionError,
    MCPLifecycleError,
    MCPServerConfig,
    StdioTransport,
)
from schemas.agents.conversation_agent import ConversationAgentOutput
from schemas.agents.planner_v2 import PlannerResult
from schemas.memory_retrieval import MemoryRetrievalResult
from schemas.orchestrator.orchestrator_v2 import (
    ConversationAgentHandoff,
    OrchestratorResult,
)


TEST_SERVER = Path(__file__).with_name("mcp_server_fixture.py")


def server_config(name: str, label: str | None = None) -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport=StdioTransport(
            command=sys.executable,
            args=(str(TEST_SERVER), label or name),
            cwd=str(PROJECT_ROOT),
        ),
    )


class EmptyMemoryRetrieval:
    def retrieve(self, query: str) -> MemoryRetrievalResult:
        return MemoryRetrievalResult(query=query, results=[])


def test_local_research_subsystem_is_discovered_and_invoked_through_mcp() -> None:
    with MCPClient(MCP_SERVERS) as client:
        catalog = client.tools()

        assert "research__research" in catalog
        assert catalog["research__research"]["input_schema"]["required"] == [
            "user_query"
        ]
        assert "Research Subsystem" in catalog["research__research"]["description"]

        result = client.call_tool(
            "research__research",
            {"user_query": ""},
        )

    assert result.ok
    assert result.data["status"] == "failed"
    assert result.data["errors"] == [
        "Research query must be a non-empty string."
    ]


def test_tools_from_multiple_servers_keep_namespaced_identity() -> None:
    with MCPClient(
        (server_config("alpha", "server-a"), server_config("beta", "server-b"))
    ) as client:
        catalog = client.tools()

        assert "alpha__echo" in catalog
        assert "beta__echo" in catalog
        assert catalog["alpha__echo"]["name"] == "alpha__echo"
        assert catalog["beta__echo"]["name"] == "beta__echo"

        result_a = client.call_tool("alpha__echo", {"value": "first"})
        result_b = client.call_tool("beta__echo", {"value": "second"})

    assert result_a.data == {"server": "server-a", "value": "first"}
    assert result_b.data == {"server": "server-b", "value": "second"}


def test_tool_errors_are_returned_as_normalized_failures() -> None:
    with MCPClient((server_config("alpha"),)) as client:
        result = client.call_tool("alpha__fail", {"message": "expected failure"})

    assert not result.ok
    assert result.is_error
    assert result.text == "Error executing tool fail"


def test_unknown_tool_is_returned_as_a_normalized_failure() -> None:
    with MCPClient((server_config("alpha"),)) as client:
        result = client.call_tool("alpha__not_registered", {})

    assert not result.ok
    assert result.is_error
    assert "Unknown tool" in (result.text or "")


def test_connection_failure_is_reported_and_client_can_be_closed() -> None:
    client = MCPClient(
        (
            MCPServerConfig(
                name="missing",
                transport=StdioTransport(command="/no/such/mcp-server"),
            ),
        )
    )

    with pytest.raises(MCPConnectionError):
        client.connect()

    client.close()


def test_closed_client_rejects_operations_and_can_be_reconnected() -> None:
    client = MCPClient((server_config("alpha"),))
    client.connect()
    client.close()

    with pytest.raises(MCPLifecycleError):
        client.tools()

    with client:
        assert "alpha__echo" in client.tools()


def test_brain_routes_dynamic_tool_arguments_and_records_result_in_runtime() -> None:
    planner_states: list[dict] = []
    orchestrator_states: list[dict] = []
    orchestrator_calls = 0

    def planner(state):
        planner_states.append(state)
        return PlannerResult(
            mode="planned",
            objective="Echo the requested value",
            steps=[
                {
                    "id": "step-1",
                    "step": "Call the discovered echo tool",
                    "status": "pending",
                }
            ],
        )

    def orchestrator(runtime_state, available_tools):
        nonlocal orchestrator_calls
        orchestrator_calls += 1
        orchestrator_states.append(runtime_state)

        if orchestrator_calls == 1:
            assert "alpha__echo" in available_tools
            return OrchestratorResult(
                next_step="execute",
                actions=[
                    {
                        "tool_name": "alpha__echo",
                        "arguments": {"value": "tool-specific argument"},
                    }
                ],
            )

        return OrchestratorResult(
            next_step="respond",
            conversation_agent_handoff=ConversationAgentHandoff(
                user_request=runtime_state["user_request"],
                objective="Report the tool result.",
            ),
        )

    brain = JarvisBrain(
        mcp_servers=(server_config("alpha", "runtime-server"),),
        planner=planner,
        orchestrator=orchestrator,
        conversation_agent=lambda state: ConversationAgentOutput(
            response="The MCP tool ran.",
            response_type="answer",
        ),
        memory_retrieval=EmptyMemoryRetrieval(),
    )

    result = brain.run("Echo this value")

    assert result.status == "success"
    assert planner_states[0]["available_tools"]["alpha__echo"]["input_schema"][
        "required"
    ] == ["value"]
    tool_result = result.state["steps"][0]["result"]
    assert tool_result["tool_name"] == "alpha__echo"
    assert tool_result["ok"] is True
    assert tool_result["result"] == {
        "server": "runtime-server",
        "value": "tool-specific argument",
    }
    assert "tool-specific argument" in tool_result["text"]
    assert tool_result["is_error"] is False
    assert orchestrator_states[1]["steps"][0]["result"] == tool_result
    assert orchestrator_calls == 2


def test_brain_records_tool_failure_for_the_next_orchestration_cycle() -> None:
    orchestrator_states: list[dict] = []
    orchestrator_calls = 0

    def orchestrator(runtime_state, available_tools):
        nonlocal orchestrator_calls
        orchestrator_calls += 1
        orchestrator_states.append(runtime_state)

        if orchestrator_calls == 1:
            return OrchestratorResult(
                next_step="execute",
                actions=[
                    {
                        "tool_name": "alpha__fail",
                        "arguments": {"message": "expected failure"},
                    }
                ],
            )

        return OrchestratorResult(
            next_step="respond",
            conversation_agent_handoff=ConversationAgentHandoff(
                user_request=runtime_state["user_request"],
                objective="Explain the tool failure.",
            ),
        )

    brain = JarvisBrain(
        mcp_servers=(server_config("alpha"),),
        planner=lambda state: PlannerResult(
            mode="direct",
        ),
        orchestrator=orchestrator,
        conversation_agent=lambda state: ConversationAgentOutput(
            response="The tool failure is recorded.",
            response_type="answer",
        ),
        memory_retrieval=EmptyMemoryRetrieval(),
    )

    result = brain.run("Run a failing tool")

    step_result = result.state["steps"][0]["result"]
    assert result.status == "success"
    assert step_result["ok"] is False
    assert step_result["text"] == "Error executing tool fail"
    assert orchestrator_states[1]["steps"][0]["result"] == step_result
