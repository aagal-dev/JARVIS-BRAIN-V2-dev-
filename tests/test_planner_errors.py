from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from integrations.base_agent import BaseAgent
from schemas.agents.planner_v2 import PlannerResult


class RateLimitedClient:
    def generate(self, **_kwargs):
        return SimpleNamespace(
            success=False,
            error="You reached the request limit (status code: 429)",
        )


def test_planner_agent_preserves_rate_limit_errors_without_mode_validation_error():
    planner = BaseAgent(
        system_prompt="",
        response_model=PlannerResult,
        client=RateLimitedClient(),
    )

    result = planner.invoke({})

    assert isinstance(result, PlannerResult)
    assert result.mode is None
    assert result.error == "You reached the request limit (status code: 429)"


def test_planner_still_requires_mode_for_successful_results():
    with pytest.raises(ValidationError, match="Planner mode is required"):
        PlannerResult()


def test_planner_generation_schema_still_requires_a_scalar_mode():
    schema = PlannerResult.model_json_schema()

    assert "mode" in schema["required"]
    assert schema["properties"]["mode"]["type"] == "string"
    assert schema["properties"]["mode"]["enum"] == ["direct", "planned"]


def test_planner_error_results_cannot_contain_partial_plan_state():
    with pytest.raises(ValidationError, match="must not include planning state"):
        PlannerResult(
            mode="planned",
            objective="Incomplete plan",
            error="Rate limit reached",
        )
