from .manager import ThreadedServiceManager
from .registry import ServiceRegistry
from .state_store import ThreadedStateStore 

from .services.time_service import TimeService

service_registry = ServiceRegistry()
service_state_store = ThreadedStateStore()

time_service = TimeService()

# registering services
service_registry.register(time_service)

# Creating service manager
service_manager = ThreadedServiceManager(
  registry=service_registry,
  state_store=service_state_store
)