from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .agents.research_executor import invoke_research_executor
from .agents.research_planner import invoke_research_planner
from .agents.synthesizer import synthesize
from .compression_pipeline.tree_summarizer_v2 import TreeSummarizer
from .connectors.connector_result_cleaner import clean_connector_results
from .connectors.connector_runtime import execute_connectors
from .connectors.connector_registry import ConnectorRegistry
from .connectors.registred_connectors import connector_registry
from .types import ConnectorExecutionSummary, ResearchResult


def _result_count(value: Any) -> int:
    if isinstance(value, (list, tuple, dict)):
        return len(value)
    return 0


def _execution_summary(
    result: Any,
    *,
    connector: str,
    query: str,
) -> ConnectorExecutionSummary:
    if not isinstance(result, Mapping):
        return ConnectorExecutionSummary(
            connector=connector,
            query=query,
            status="success",
        )

    status = str(result.get("status") or ("failed" if result.get("error") else "success"))
    nested_results = result.get("results")
    return ConnectorExecutionSummary(
        connector=str(result.get("connector") or connector),
        query=str(result.get("query") or query),
        status=status,
        result_count=_result_count(nested_results),
    )


def _synthesis_value(value: Any) -> str | dict[str, Any] | None:
    if isinstance(value, (str, dict)):
        return value
    if value is None:
        return None
    return str(value)


def _synthesis_error(value: str | dict[str, Any] | None) -> str | None:
    if value is None:
        return "Research synthesizer returned no result."
    if isinstance(value, dict):
        return None

    lowered = value.strip().lower()
    if not lowered:
        return "Research synthesizer returned an empty result."
    if lowered.startswith(
        (
            "request error",
            "http error",
            "invalid structure",
            "no content field",
            "no message field",
            "synthesizer faild:",
        )
    ):
        return "Research synthesizer failed to produce a valid synthesis."
    return None


def _failed(query: str, message: str) -> ResearchResult:
    return ResearchResult(status="failed", query=query, errors=[message])


def invoke_research_subsystem(
    user_query: str,
    *,
    planner: Callable[[str], Any] = invoke_research_planner,
    executor: Callable[[Any], Any] = invoke_research_executor,
    registry: ConnectorRegistry = connector_registry,
    connector_runner: Callable[[list[Any], str], list[Any]] = execute_connectors,
    summarizer_factory: Callable[[], TreeSummarizer] = TreeSummarizer,
    synthesizer: Callable[[Any, str], Any] = synthesize,
) -> ResearchResult:
    """Run the original research pipeline and return a Brain-safe result."""
    query = str(user_query or "").strip()
    if not query:
        return _failed(query, "Research query must be a non-empty string.")

    try:
        plan = planner(query)
        execution_plan = executor(plan)
    except Exception as exc:
        return _failed(query, f"Research planning/execution setup failed: {exc}")

    if not isinstance(execution_plan, Mapping):
        return _failed(query, "Research executor returned an invalid execution plan.")

    raw_connector_results: list[Any] = []
    execution_summaries: list[ConnectorExecutionSummary] = []
    errors: list[str] = []

    for subquery_id, subquery in execution_plan.items():
        if not isinstance(subquery, Mapping):
            errors.append(f"{subquery_id}: invalid sub-query execution.")
            continue

        executions = subquery.get("executions", [])
        if not isinstance(executions, list):
            errors.append(f"{subquery_id}: executions must be a list.")
            continue

        for execution in executions:
            if not isinstance(execution, Mapping):
                errors.append(f"{subquery_id}: invalid execution entry.")
                continue

            execution_query = str(execution.get("query") or "").strip()
            connector_names = execution.get("connectors", [])
            if not execution_query or not isinstance(connector_names, list):
                errors.append(
                    f"{subquery_id}: execution requires a query and connector list."
                )
                continue

            try:
                connectors = registry.get_many(connector_names)
                if not connectors:
                    errors.append(f"{subquery_id}: no connectors selected.")
                    continue
                results = connector_runner(connectors, execution_query)
            except Exception as exc:
                errors.append(
                    f"{subquery_id} ({execution_query}): connector execution failed: {exc}"
                )
                continue

            raw_connector_results.extend(results or [])
            for result in results or []:
                summary = _execution_summary(
                    result,
                    connector=",".join(str(name) for name in connector_names),
                    query=execution_query,
                )
                execution_summaries.append(summary)
                if summary.status in {
                    "failed",
                    "error",
                    "partial",
                    "partial_failure",
                }:
                    if isinstance(result, Mapping):
                        detail = result.get("error") or result.get("errors")
                    else:
                        detail = None
                    errors.append(
                        f"{summary.connector} ({summary.query}) failed"
                        + (f": {detail}" if detail else "")
                    )

    if not execution_summaries:
        errors.append("Research produced no connector results.")

    try:
        cleaned_results = clean_connector_results(raw_connector_results)
        summarized_results = summarizer_factory().run(cleaned_results)
        synthesized_results = synthesizer(
            connector_results=summarized_results,
            query=query,
        )
        synthesis = _synthesis_value(synthesized_results)
        synthesis_error = _synthesis_error(synthesis)
        if synthesis_error:
            errors.append(synthesis_error)
    except Exception as exc:
        return ResearchResult(
            status="failed" if not execution_summaries else "partial",
            query=query,
            connector_executions=execution_summaries,
            errors=[*errors, f"Research synthesis failed: {exc}"],
        )

    status = "success" if not errors else (
        "failed" if not execution_summaries else "partial"
    )
    return ResearchResult(
        status=status,
        query=query,
        synthesis=synthesis,
        connector_executions=execution_summaries,
        errors=errors,
    )