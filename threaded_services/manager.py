from datetime import datetime, timezone
import threading
from typing import Any

from schemas.service_state import ServiceState, ServiceStatus
from .registry import ServiceRegistry
from .service import ThreadedService
from .state_store import ThreadedStateStore


class ThreadedServiceManager:
    """Starts, runs, and stops registered services while publishing their states."""

    def __init__(
        self,
        registry: ServiceRegistry,
        state_store: ThreadedStateStore,
    ) -> None:
        self.registry = registry
        self.state_store = state_store

        self._threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def start(self, name: str) -> None:
        service = self.registry.get(name)

        if service is None:
            raise KeyError(f"service not registered: {name}")

        with self._lock:
            thread = self._threads.get(name)

            if thread is not None and thread.is_alive():
                return

            stop_event = threading.Event()

            thread = threading.Thread(
                target=self._run_service,
                args=(service, stop_event),
                name=f"threaded-service:{name}",
                daemon=True,
            )

            self._stop_events[name] = stop_event
            self._threads[name] = thread

            thread.start()

    def start_all(self) -> None:
        for name in self.registry.all():
            self.start(name)

    def stop(self, name: str) -> None:
        with self._lock:
            stop_event = self._stop_events.get(name)
            thread = self._threads.get(name)

        if stop_event is None:
            return

        stop_event.set()

        if thread is not None and thread is not threading.current_thread():
            thread.join()

        with self._lock:
            self._stop_events.pop(name, None)
            self._threads.pop(name, None)

        self._publish(
            service=name,
            status="stopped",
            data={},
            error=None,
        )

    def stop_all(self) -> None:
        for name in list(self.registry.all()):
            self.stop(name)

    def is_running(self, name: str) -> bool:
        with self._lock:
            thread = self._threads.get(name)

            return thread is not None and thread.is_alive()

    def _run_service(
        self,
        service: ThreadedService,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            try:
                data = service.update()

                if not isinstance(data, dict):
                    data = dict(data)

                self._publish(
                    service=service.name,
                    status="running",
                    data=data,
                    error=None,
                )

            except Exception as exc:
                self._publish(
                    service=service.name,
                    status="error",
                    data={},
                    error=str(exc),
                )

            stop_event.wait(service.interval)

    def _publish(
        self,
        service: str,
        status: ServiceStatus,
        data: dict[str, Any],
        error: str | None,
    ) -> None:
        self.state_store.set(
            ServiceState(
                service=service,
                status=status,
                updated_at=datetime.now(timezone.utc),
                data=data,
                error=error,
            )
        )