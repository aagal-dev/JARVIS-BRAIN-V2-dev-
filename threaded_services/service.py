from abc import ABC, abstractmethod
from collections.abc import Mapping
import math
from typing import Any


class ThreadedService(ABC):
    """Base contract for a background service managed by ThreadedServiceManager."""

    def __init__(self, name: str, interval: float) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")

        if (
            not isinstance(interval, (int, float))
            or not math.isfinite(interval)
            or interval <= 0
        ):
            raise ValueError("interval must be a finite number greater than 0")

        self.name = name.strip()
        self.interval = float(interval)

    @abstractmethod
    def update(self) -> Mapping[str, Any]:
        """Return the service's latest state."""
        raise NotImplementedError