from collections.abc import Mapping, Sequence
from typing import Any, Literal

from schemas.runtime_state import RuntimeState, RuntimeStep


RuntimeStepStatus = Literal["pending", "in_progress", "completed"]


class RuntimeStateNotInitializedError(RuntimeError):
    """Raised when a runtime state is requested before a runtime starts."""


class RuntimeStateManager:
    """Owns the lifecycle of the semantic state for one active runtime."""

    def __init__(self) -> None:
        self._state: RuntimeState | None = None
        self._completed = False

    @property
    def is_complete(self) -> bool:
        return self._completed

    def create(
        self,
        user_request: str,
        objective: str | None = None,
        steps: Sequence[RuntimeStep | Mapping[str, Any]] | None = None,
        current_step_id: str | None = None,
    ) -> RuntimeState:
        runtime_steps = [
            step if isinstance(step, RuntimeStep) else RuntimeStep.model_validate(step)
            for step in (steps or [])
        ]
        self._state = RuntimeState(
            user_request=user_request,
            objective=objective if objective is not None else "No objective decleared.",
            steps=runtime_steps,
            current_step_id=current_step_id,
        )
        self._validate_current_step()
        self._completed = False
        return self.get()

    def get(self) -> RuntimeState:
        if self._state is None:
            raise RuntimeStateNotInitializedError(
                "Runtime state has not been initialized."
            )
        return self._state.model_copy(deep=True)

    def update(self, state: RuntimeState | Mapping[str, Any]) -> RuntimeState:
        updated_state = (
            state
            if isinstance(state, RuntimeState)
            else RuntimeState.model_validate(state)
        )
        self._state = updated_state.model_copy(deep=True)
        self._validate_current_step()
        self._completed = False
        return self.get()

    def save(self, state: RuntimeState | Mapping[str, Any] | None = None) -> RuntimeState:
        """Persist the current semantic state in this active runtime manager."""
        if state is not None:
            return self.update(state)
        return self.get()

    def persist(self, state: RuntimeState | Mapping[str, Any] | None = None) -> RuntimeState:
        """Alias for save, keeping persistence separate from the semantic model."""
        return self.save(state)

    def set_current_step(self, step_id: str | None) -> RuntimeState:
        state = self._require_state()
        if step_id is None:
            state.current_step_id = None
            self._state = state
            return self.get()

        step = self._find_step(step_id)
        if state.current_step_id and state.current_step_id != step_id:
            previous_step = self._find_step(state.current_step_id)
            if previous_step.status == "in_progress":
                previous_step.status = "completed"

        step.status = "in_progress"
        state.current_step_id = step_id
        self._state = state
        self._completed = False
        return self.get()

    def update_step_status(
        self,
        step_id: str,
        status: RuntimeStepStatus,
    ) -> RuntimeState:
        state = self._require_state()
        step = self._find_step(step_id)
        step.status = status

        if status == "in_progress":
            if state.current_step_id and state.current_step_id != step_id:
                previous_step = self._find_step(state.current_step_id)
                if previous_step.status == "in_progress":
                    previous_step.status = "completed"
            state.current_step_id = step_id
        elif state.current_step_id == step_id:
            state.current_step_id = None

        self._state = state
        self._completed = False
        return self.get()

    def update_step_result(self, step_id: str, result: str | None) -> RuntimeState:
        """Attach the grounded outcome of a step without changing its status."""
        state = self._require_state()
        step = self._find_step(step_id)
        step.result = result
        self._state = state
        self._completed = False
        return self.get()

    def complete(self) -> RuntimeState:
        state = self._require_state()
        if state.current_step_id is not None:
            current_step = self._find_step(state.current_step_id)
            if current_step.status == "in_progress":
                current_step.status = "completed"
            state.current_step_id = None
        self._state = state
        self._completed = True
        return self.get()

    def _require_state(self) -> RuntimeState:
        if self._state is None:
            raise RuntimeStateNotInitializedError(
                "Runtime state has not been initialized."
            )
        return self._state

    def _find_step(self, step_id: str) -> RuntimeStep:
        state = self._require_state()
        for step in state.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"Unknown runtime step: {step_id}")

    def _validate_current_step(self) -> None:
        state = self._require_state()
        if state.current_step_id is not None:
            self._find_step(state.current_step_id)