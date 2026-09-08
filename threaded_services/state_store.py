from copy import deepcopy
from threading import RLock

from schemas.service_state import ServiceState


class ThreadedStateStore:
    """Thread-safe storage for the latest state published by each service."""

    def __init__(self) -> None:
        self._states: dict[str, ServiceState] = {}
        self._lock = RLock()

    def set(self, state: ServiceState) -> None:
        with self._lock:
            self._states[state.service] = deepcopy(state)

    def get(self, service: str) -> ServiceState | None:
        with self._lock:
            state = self._states.get(service)
            return deepcopy(state) if state is not None else None

    def snapshot(self) -> dict[str, ServiceState]:
        with self._lock:
            return deepcopy(self._states)

    def remove(self, service: str) -> None:
        with self._lock:
            self._states.pop(service, None)