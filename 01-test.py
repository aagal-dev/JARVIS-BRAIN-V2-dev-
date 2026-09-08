from threaded_services.manager import ThreadedServiceManager
from threaded_services.registry import ServiceRegistry
from threaded_services.state_store import ThreadedStateStore 

from threaded_services.services.time_service import TimeService

import time
import json

service_registry = ServiceRegistry()
service_state_store = ThreadedStateStore()

time_service = TimeService()

service_registry.register(time_service)

service_manager = ThreadedServiceManager(
  registry=service_registry,
  state_store=service_state_store
)

service_manager.start_all()
print("\nStarted all threaded services...")

try:
  for _ in range(5):
    time.sleep(1)

    snapshot = service_state_store.snapshot()["time"]

    service_state = snapshot.model_dump()
    
    print(f"\nLive state: \n{json.dumps(service_state, indent=2, default=str)}")

finally:
  service_manager.stop_all()

  print("\nStopped all threaded services...")