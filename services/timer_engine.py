"""
Core business logic for evaluating timer transitions.

This module is pure and side-effect free. It defines how a new OCR reading
from a timer updates the system's tracked state, and determines whether an
alert should be dispatched.
"""

from dataclasses import dataclass

from models import AlertEvent, TimerState

# Special value indicating a timer is not currently tracking an active challenge
DEFAULT_TIMER_VALUE = 6000

# Minimum valid reading for a new challenge trigger. 
# Prevents OCR hallucinations (e.g. reading '12' randomly) from triggering an alert.
MIN_VALID_TRIGGER_TIME = 100

# Cooldown period before a timer that bounced to a higher value can trigger a new alert.
# Helps prevent double-alerting if the stream jumps or the timer resets briefly.
OVERLAP_REARM_SECONDS = 1200

# Threshold for a "big bounce" (e.g. timer was 40:00, now it's 50:00)
# If the timer bounces by more than this amount, we treat it as a new challenge.
BIG_BOUNCE_SECONDS = 1000

# Transition case names for categorization/logging
CASE_IDLE_TRIGGER = "idle_trigger"
CASE_TRIGGER_FROM_ZERO = "trigger_from_zero"
CASE_DECREMENT = "decrement"
CASE_RESET = "reset"
CASE_OVERLAP_TRIGGER = "overlap_trigger"
CASE_OVERLAP_DEFER = "overlap_defer"
CASE_UNCHANGED = "unchanged"


@dataclass(frozen=True)
class TimerTransition:
    """Result of evaluating a timer reading against the current state."""
    timer_state: TimerState
    case: str
    alert_event: AlertEvent | None = None
    ignored_low_value: bool = False


def evaluate_timer_transition(timer_index: int, current_time: int, tracked_timer: TimerState, now: int) -> TimerTransition:
    """
    Evaluate the new state of a timer and return any resultant events.

    Args:
        timer_index: Position of the timer (used for alert generation).
        current_time: The newly scraped timer reading (as an integer).
        tracked_timer: The current persisted state for this timer.
        now: The current unix epoch time in seconds.

    Returns:
        A TimerTransition containing the updated TimerState, the transition case name,
        and optionally an AlertEvent to notify users.
    """
    tracked_time = tracked_timer.tracked_time
    last_reset_time = tracked_timer.last_reset_time

    # SPECIAL CASE: Ignore 5000 readings for timer 1 due to overlapping text
    if timer_index == 0 and current_time == 5000:
        return TimerTransition(timer_state=tracked_timer, case=CASE_UNCHANGED)

    # CASE 0: Ignore 0 readings when we are already idle to prevent bouncing.
    if current_time == 0 and tracked_time == DEFAULT_TIMER_VALUE:
        return TimerTransition(timer_state=tracked_timer, case=CASE_UNCHANGED)

    # CASE 1: Normal trigger. Timer was idle (6000) and now shows a valid countdown.
    if current_time < tracked_time and tracked_time == DEFAULT_TIMER_VALUE and current_time != 0:
        # Ignore extremely low initial values as likely OCR garbage.
        if current_time < MIN_VALID_TRIGGER_TIME:
            return TimerTransition(
                timer_state=tracked_timer,
                case=CASE_IDLE_TRIGGER,
                ignored_low_value=True,
            )

        next_state = TimerState(
            tracked_time=current_time,
            has_alerted=True,
            last_reset_time=last_reset_time,
        )
        alert_event = None
        # Only create an alert if we haven't technically alerted for this tracking session
        if not tracked_timer.has_alerted:
            alert_event = AlertEvent(timer_position=timer_index + 1, time_remaining=current_time)

        return TimerTransition(
            timer_state=next_state,
            case=CASE_IDLE_TRIGGER,
            alert_event=alert_event,
        )

    # CASE 1b: Trigger from 0. Timer hit 0 on previous tick, and now shows a new countdown.
    # We bypass overlap cooldowns because hitting 0 means the previous challenge definitively ended.
    if tracked_time == 0 and current_time > 0 and current_time != DEFAULT_TIMER_VALUE:
        if current_time < MIN_VALID_TRIGGER_TIME:
            return TimerTransition(
                timer_state=tracked_timer,
                case=CASE_TRIGGER_FROM_ZERO,
                ignored_low_value=True,
            )

        next_state = TimerState(
            tracked_time=current_time,
            has_alerted=True,
            last_reset_time=now,  # Start a fresh challenge
        )
        return TimerTransition(
            timer_state=next_state,
            case=CASE_TRIGGER_FROM_ZERO,
            alert_event=AlertEvent(timer_position=timer_index + 1, time_remaining=current_time),
        )

    # CASE 2: Normal decrement. Timer is continuing to count down.
    # Note: this also covers cases where a timer was triggered, but the original OCR
    # read was slightly too high, so we keep walking it downwards without sending a new alert.
    if current_time < tracked_time:
        next_state = TimerState(
            tracked_time=current_time,
            has_alerted=tracked_timer.has_alerted,
            last_reset_time=last_reset_time,
        )
        return TimerTransition(timer_state=next_state, case=CASE_DECREMENT)

    # CASE 3: Reset. Timer has either hit exactly 0, or explicitly returned to the idle marker.
    if current_time == 0 or current_time == DEFAULT_TIMER_VALUE:
        next_state = TimerState(
            tracked_time=DEFAULT_TIMER_VALUE,
            has_alerted=False,
            last_reset_time=now,
        )
        return TimerTransition(timer_state=next_state, case=CASE_RESET)

    # CASE 4 & 5: Overlap or bounce. The new reading is higher than the currently tracked time.
    # This could mean a new challenge started right on top of an old one (or stream jumped backwards).
    if current_time > tracked_time:
        # If enough time has passed since the timer last reset, we treat it as a new valid challenge.
        if now > (last_reset_time + OVERLAP_REARM_SECONDS):
            # Safety check against hallucinated low values
            if current_time < MIN_VALID_TRIGGER_TIME:
                return TimerTransition(
                    timer_state=tracked_timer,
                    case=CASE_OVERLAP_TRIGGER,
                    ignored_low_value=True,
                )

            # TODO: implement this
            # Safety check on odd bounces, specifically around the 40 minute mark, e.g. going from 31 -> 39
            # Only trigger if the new time is less than 4000 (40 minutes)

            next_state = TimerState(
                tracked_time=current_time,
                has_alerted=True,
                last_reset_time=now,  # Treating this as a fresh start
            )
            return TimerTransition(
                timer_state=next_state,
                case=CASE_OVERLAP_TRIGGER,
                alert_event=AlertEvent(timer_position=timer_index + 1, time_remaining=current_time),
            )

        # Still within the cooldown period (e.g. OCR just bounced around 45:10 then read 45:15).
        # We update the tracked time so it reflects reality, but we don't spam a second alert.
        next_state = TimerState(
            tracked_time=current_time,
            has_alerted=False,  # Don't consider this a valid 'alerted' run since it was just a bounce
            last_reset_time=last_reset_time,
        )
        return TimerTransition(timer_state=next_state, case=CASE_OVERLAP_DEFER)

    # CASE 6: Unchanged. The current reading exactly matches what we already knew.
    return TimerTransition(timer_state=tracked_timer, case=CASE_UNCHANGED)
