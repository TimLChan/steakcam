"""Unit tests for win detection in the timer engine."""

import unittest

from models import TimerState, WinEvent
from services.timer_engine import (
    CASE_DECREMENT,
    CASE_OVERLAP_DEFER,
    CASE_RESET,
    CASE_TRIGGER_FROM_ZERO,
    CASE_UNCHANGED,
    CASE_WIN,
    DEFAULT_TIMER_VALUE,
    evaluate_timer_transition,
)

START = 1_000_000  # epoch time the tracked challenge started


def run_sequence(readings, state=None, timer_index=2, start_now=START + 60):
    """Feed *readings* through the engine one poll at a time.

    ``None`` represents a blank OCR read, which the poller skips entirely.
    Returns the list of transitions and the final state.
    """
    if state is None:
        state = TimerState(tracked_time=DEFAULT_TIMER_VALUE, has_alerted=False, last_reset_time=START)
    transitions = []
    now = start_now
    for reading in readings:
        now += 75
        if reading is None:
            continue
        transition = evaluate_timer_transition(timer_index, reading, state, now)
        transitions.append(transition)
        state = transition.timer_state
    return transitions, state


def wins(transitions):
    return [t.win_event for t in transitions if t.win_event is not None]


class TestWinDetection(unittest.TestCase):

    # ------------------------------------------------------------------
    # Scenarios from issue #5
    # ------------------------------------------------------------------

    def test_same_reading_twice_is_a_win(self):
        transitions, state = run_sequence([3221, 3221])
        self.assertEqual(transitions[-1].case, CASE_WIN)
        self.assertEqual(wins(transitions), [WinEvent(timer_position=3, time_remaining=3221, challenge_started_at=START)])
        self.assertTrue(state.has_won)

    def test_reset_to_6000_is_not_a_win(self):
        transitions, _ = run_sequence([3221, 6000])
        self.assertEqual(transitions[-1].case, CASE_RESET)
        self.assertEqual(wins(transitions), [])

    def test_reset_to_0_is_not_a_win(self):
        # 0 is lower than the tracked time, so it's tracked as a decrement down to 0
        transitions, state = run_sequence([3221, 0])
        self.assertEqual(state.tracked_time, 0)
        self.assertEqual(wins(transitions), [])

    def test_counting_down_is_not_a_win(self):
        transitions, _ = run_sequence([3221, 3110])
        self.assertEqual(transitions[-1].case, CASE_DECREMENT)
        self.assertEqual(wins(transitions), [])

    def test_timer_going_up_is_not_a_win(self):
        transitions, _ = run_sequence([3221, 3300])
        self.assertNotEqual(transitions[-1].case, CASE_WIN)
        self.assertEqual(wins(transitions), [])

    def test_blank_ocr_does_not_break_consecutive_readings(self):
        transitions, _ = run_sequence([3221, None, 3221])
        self.assertEqual(len(wins(transitions)), 1)

    def test_zero_between_equal_readings_is_not_a_win(self):
        transitions, state = run_sequence([3221, 0, 3221])
        self.assertEqual(transitions[-1].case, CASE_TRIGGER_FROM_ZERO)
        self.assertEqual(wins(transitions), [])
        self.assertFalse(state.has_won)

    # ------------------------------------------------------------------
    # One win per challenge
    # ------------------------------------------------------------------

    def test_stopped_clock_only_wins_once(self):
        transitions, state = run_sequence([3221, 3221, 3221, 3221])
        self.assertEqual(len(wins(transitions)), 1)
        self.assertEqual(transitions[-1].case, CASE_UNCHANGED)
        self.assertTrue(state.has_won)

    def test_reset_allows_a_new_win(self):
        transitions, state = run_sequence([3221, 3221, 6000, 5900, 5800, 5800])
        self.assertEqual(len(wins(transitions)), 2)
        self.assertEqual(wins(transitions)[1].time_remaining, 5800)

    def test_bounce_on_stopped_clock_keeps_has_won(self):
        # Within the overlap cooldown a higher misread is treated as a bounce.
        transitions, state = run_sequence([3221, 3221, 3881, 3221, 3221])
        self.assertIn(CASE_OVERLAP_DEFER, [t.case for t in transitions])
        self.assertEqual(len(wins(transitions)), 1)
        self.assertTrue(state.has_won)

    def test_decrement_preserves_has_won(self):
        state = TimerState(tracked_time=3221, has_alerted=True, last_reset_time=START, has_won=True)
        transitions, state = run_sequence([3100], state=state)
        self.assertEqual(transitions[-1].case, CASE_DECREMENT)
        self.assertTrue(state.has_won)

    # ------------------------------------------------------------------
    # Clocks stopped right after starting
    # ------------------------------------------------------------------

    def test_clock_stopped_in_first_two_minutes_is_not_a_win(self):
        transitions, state = run_sequence([5959, 5959, 5959])
        self.assertEqual([t.case for t in transitions[1:]], [CASE_UNCHANGED, CASE_UNCHANGED])
        self.assertEqual(wins(transitions), [])
        self.assertFalse(state.has_won)

    def test_clock_stopped_at_two_minutes_is_a_win(self):
        transitions, _ = run_sequence([5800, 5800])
        self.assertEqual(transitions[-1].case, CASE_WIN)

    def test_wrong_clock_restarted_can_still_win(self):
        transitions, state = run_sequence([5959, 5959, 6000, 4500, 3221, 3221])
        self.assertEqual(len(wins(transitions)), 1)
        self.assertEqual(wins(transitions)[0].time_remaining, 3221)
        self.assertTrue(state.has_won)

    def test_idle_and_zero_readings_never_win(self):
        transitions, _ = run_sequence([6000, 6000, 6000, 0, 0, 0])
        self.assertEqual(wins(transitions), [])


class TestTimerStateLegacy(unittest.TestCase):

    def test_from_legacy_three_elements_defaults_has_won(self):
        state = TimerState.from_legacy([3221, True, START])
        self.assertEqual(state, TimerState(3221, True, START, False))

    def test_from_legacy_four_elements(self):
        state = TimerState.from_legacy([3221, True, START, True])
        self.assertTrue(state.has_won)

    def test_round_trip(self):
        state = TimerState(3221, True, START, True)
        self.assertEqual(TimerState.from_legacy(state.to_legacy()), state)


if __name__ == "__main__":
    unittest.main()
