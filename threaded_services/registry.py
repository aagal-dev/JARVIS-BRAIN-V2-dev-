from .service import ThreadedService


class ServiceRegistry:
    """Registry of services available to the threaded service manager."""

    def __init__(self) -> None:
        self._services: dict[str, ThreadedService] = {}

    def register(self, service: ThreadedService) -> None:
        if not isinstance(service, ThreadedService):
            raise TypeError("service must be a ThreadedService")

        if service.name in self._services:
            raise ValueError(f"service already registered: {service.name}")

        self._services[service.name] = service

    def unregister(self, name: str) -> ThreadedService:
        try:
            return self._services.pop(name)
        except KeyError as exc:
            raise KeyError(f"service not registered: {name}") from exc

    def get(self, name: str) -> ThreadedService | None:
        return self._services.get(name)

    def all(self) -> dict[str, ThreadedService]:
        return dict(self._services)