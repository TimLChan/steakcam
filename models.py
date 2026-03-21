from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TimerState:
    tracked_time: int
    has_alerted: bool
    last_reset_time: int

    @classmethod
    def from_legacy(cls, payload: Iterable[Any]) -> "TimerState":
        tracked_time, has_alerted, last_reset_time = payload
        return cls(
            tracked_time=int(tracked_time),
            has_alerted=bool(has_alerted),
            last_reset_time=int(last_reset_time),
        )

    def to_legacy(self) -> tuple[int, bool, int]:
        return (self.tracked_time, self.has_alerted, self.last_reset_time)


@dataclass(frozen=True)
class AlertEvent:
    timer_position: int
    time_remaining: int
