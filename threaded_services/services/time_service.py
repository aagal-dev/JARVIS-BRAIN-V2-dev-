from datetime import datetime
from typing import Any

from threaded_services.service import ThreadedService


class TimeService(ThreadedService):
    """
    Provides the current local temporal state of the host system.

    The service is deterministic with respect to the system clock and
    requires no external services.
    """

    def __init__(self, interval: float = 1.0) -> None:
        super().__init__(
            name="time",
            interval=interval,
        )

    def update(self) -> dict[str, Any]:
        now = datetime.now().astimezone()

        return {
            "current": {
                "date": now.date().isoformat(),
                "time": now.strftime("%H:%M:%S"),
                "datetime": now.isoformat(),
            },
            "timezone": {
                "name": now.tzname(),
                "utc_offset": now.utcoffset().total_seconds()
                if now.utcoffset() is not None
                else None,
            },
            "calendar": {
                "weekday": now.strftime("%A"),
                "day_of_week": now.isoweekday(),
                "day_of_month": now.day,
                "day_of_year": now.timetuple().tm_yday,
                "week_of_year": now.isocalendar().week,
                "month": now.strftime("%B"),
                "month_number": now.month,
                "year": now.year,
            },
            "temporal": {
                "period": self._get_period(now.hour),
                "is_weekend": now.weekday() >= 5,
                "is_leap_year": self._is_leap_year(now.year),
            },
            "unix_timestamp": now.timestamp(),
        }

    @staticmethod
    def _get_period(hour: int) -> str:
        if 5 <= hour < 12:
            return "morning"

        if 12 <= hour < 17:
            return "afternoon"

        if 17 <= hour < 21:
            return "evening"

        return "night"

    @staticmethod
    def _is_leap_year(year: int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)