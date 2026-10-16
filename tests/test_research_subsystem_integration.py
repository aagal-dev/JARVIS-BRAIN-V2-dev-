from __future__ import annotations

from subsystems.research_subsystem.research_workflow import (
    invoke_research_subsystem,
)
from subsystems.research_subsystem.types import ResearchResult
from subsystems.research_subsystem.mcp_server import research


class StubConnector:
    name = "stub"

    def execute(self, query: str) -> dict[str, Any]:
        return {
            "connector": self.name,
            "query": query,
            "results": [
                {
                    "title": "A grounded source",
                    "url": "https://example.test/source",
                    "text": (
                        "This is sufficiently long grounded evidence for the "
                        "cleaner and summarizer test path."
                    ),
                }
            ],
        }


class StubRegistry:
    def get_many(self, names: list[str]) -> list[StubConnector]:
        assert names == ["stub"]
        return [StubConnector()]


class StubSummarizer:
    def run(self, results: Any) -> str:
        assert len(results) == 1
        return "Compressed grounded evidence."


def test_research_pipeline_returns_typed_result_without_raw_connector_payloads() -> None:
    result = invoke_research_subsystem(
        "Explain the test topic",
        planner=lambda query: {"main_goal": query},
        executor=lambda plan: {
            "sq_1": {
                "executions": [
                    {"query": "focused test topic", "connectors": ["stub"]}
                ]
            }
        },
        registry=StubRegistry(),
        summarizer_factory=StubSummarizer,
        synthesizer=lambda connector_results, query: {
            "overview": connector_results,
            "key_findings": ["The test path completed."],
        },
    )

    assert isinstance(result, ResearchResult)
    assert result.status == "success"
    assert result.synthesis == {
        "overview": "Compressed grounded evidence.",
        "key_findings": ["The test path completed."],
    }
    assert result.connector_executions[0].connector == "stub"
    assert result.connector_executions[0].result_count == 1
    assert "results" not in result.model_dump()


def test_research_mcp_tool_adapts_subsystem_result_to_json() -> None:
    result = research("")

    assert result["status"] == "failed"
    assert result["query"] == ""
    assert result["errors"] == ["Research query must be a non-empty string."]


def test_research_mcp_tool_serializes_a_successful_subsystem_result(
    monkeypatch,
) -> None:
    expected = ResearchResult(
        status="success",
        query="Explain the test topic",
        synthesis={"key_findings": ["The finding is grounded."]},
    )
    monkeypatch.setattr(
        "subsystems.research_subsystem.mcp_server.invoke_research_subsystem",
        lambda query: expected,
    )

    assert research("Explain the test topic") == expected.model_dump(mode="json")
