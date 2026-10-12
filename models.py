from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TimerState:
    tracked_time: int
    has_alerted: bool
    last_reset_time: int
    has_won: bool = False

    @classmethod
    def from_legacy(cls, payload: Iterable[Any]) -> "TimerState":
        # Accepts the original 3-element tuple as well as the 4-element tuple with has_won
        tracked_time, has_alerted, last_reset_time, *rest = payload
        return cls(
            tracked_time=int(tracked_time),
            has_alerted=bool(has_alerted),
            last_reset_time=int(last_reset_time),
            has_won=bool(rest[0]) if rest else False,
        )

    def to_legacy(self) -> tuple[int, bool, int, bool]:
        return (self.tracked_time, self.has_alerted, self.last_reset_time, self.has_won)


@dataclass(frozen=True)
class AlertEvent:
    timer_position: int
    time_remaining: int


@dataclass(frozen=True)
class WinEvent:
    timer_position: int
    time_remaining: int
    challenge_started_at: int
