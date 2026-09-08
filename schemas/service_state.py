from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


ServiceStatus = Literal["running", "error", "stopped"]


class ServiceState(BaseModel):
    model_config = ConfigDict(frozen=True)

    service: str
    status: ServiceStatus
    updated_at: datetime
    data: dict[str, Any]
    error: str | None = None