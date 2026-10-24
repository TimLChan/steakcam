"""Integration tests for poller-streaming interaction."""

import time
import unittest
from unittest.mock import MagicMock, call, patch

from models import TimerState
from services.poller import run_once
from services.timer_engine import CASE_IDLE_TRIGGER, CASE_UNCHANGED


class TestPollerStreaming(unittest.TestCase):
    """Test poller's integration with StreamManager."""

    def setUp(self):
        """Set up common mocks for all tests."""
        self.settings = MagicMock()
        self.settings.timezone = "US/Central"
        self.settings.should_send_wrapup = False
        self.settings.video_url = "http://angelcam.example.com/stream"
        self.settings.streaming_enabled = True
        self.settings.public_stream_url = "https://youtube.com/watch?v=test"

        self.state = MagicMock()
        self.state.wrapup_sent_today = False
        # Idle timers: [tracked_time=6000, has_alerted=False, last_reset_time=0]
        self.state.tracked_timers = [[6000, False, 0]] * 6

        self.angelcam = MagicMock()
        self.pipeline = MagicMock()
        self.notifier = MagicMock()
        self.stream_manager = MagicMock()
        self.stream_manager.is_streaming = False

    @patch("services.poller.helper")
    @patch("services.poller.evaluate_timer_transition")
    @patch("time.time")
    def test_stream_triggered_on_alert(self, mock_time, mock_evaluate, mock_helper):
        """Verify on_challenge_started called with correct params when alert occurs."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = True
        mock_helper.getDateTime.return_value = "2024-01-15 12:00:00"

        # Set up angelcam to return valid m3u8 URL and video
        m3u8_url = "http://angelcam.example.com/playlist.m3u8"
        self.angelcam.get_m3u8.return_value = (m3u8_url, False)
        self.angelcam.download_video.return_value = ("/tmp/video.mp4", False)

        # Pipeline returns 6 timer readings - timer 0 has 4000 (alert), others idle
        self.pipeline.get_frames.return_value = ["4000", "6000", "6000", "6000", "6000", "6000"]

        # Only timer 0 triggers an alert, others return no-change transitions
        alert_transition = MagicMock()
        alert_transition.case = CASE_IDLE_TRIGGER
        alert_transition.ignored_low_value = False
        alert_transition.alert_event = MagicMock(timer_position=1, time_remaining=4000)
        alert_transition.timer_state = TimerState(tracked_time=4000, has_alerted=True, last_reset_time=0)

        idle_transition = MagicMock()
        idle_transition.case = CASE_UNCHANGED
        idle_transition.ignored_low_value = False
        idle_transition.alert_event = None
        idle_transition.timer_state = TimerState(tracked_time=6000, has_alerted=False, last_reset_time=0)

        # First call (timer 0) alerts, rest are idle
        mock_evaluate.side_effect = [alert_transition] + [idle_transition] * 5

        # Run poller (not first poll)
        run_once(
            first=False,
            daily_challenge_count=0,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify stream_manager.on_challenge_started was called with m3u8_url and current timestamp
        self.stream_manager.on_challenge_started.assert_called_once_with(m3u8_url, 1234567890)

    @patch("services.poller.helper")
    @patch("services.poller.evaluate_timer_transition")
    @patch("time.time")
    def test_stream_suppressed_on_first_poll(self, mock_time, mock_evaluate, mock_helper):
        """Verify on_challenge_started NOT called when first=True."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = True
        mock_helper.getDateTime.return_value = "2024-01-15 12:00:00"

        m3u8_url = "http://angelcam.example.com/playlist.m3u8"
        self.angelcam.get_m3u8.return_value = (m3u8_url, False)
        self.angelcam.download_video.return_value = ("/tmp/video.mp4", False)
        self.pipeline.get_frames.return_value = ["6000", "6000", "6000", "6000", "6000", "6000"]

        # Only timer 0 triggers an alert, others return no-change transitions
        alert_transition = MagicMock()
        alert_transition.case = CASE_IDLE_TRIGGER
        alert_transition.ignored_low_value = False
        alert_transition.alert_event = MagicMock(timer_position=1, time_remaining=6000)
        alert_transition.timer_state = TimerState(tracked_time=6000, has_alerted=True, last_reset_time=0)

        idle_transition = MagicMock()
        idle_transition.case = CASE_UNCHANGED
        idle_transition.ignored_low_value = False
        idle_transition.alert_event = None
        idle_transition.timer_state = TimerState(tracked_time=6000, has_alerted=False, last_reset_time=0)

        # First call (timer 0) alerts, rest are idle
        mock_evaluate.side_effect = [alert_transition] + [idle_transition] * 5

        # Run poller with first=True
        run_once(
            first=True,
            daily_challenge_count=0,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify stream_manager.on_challenge_started was NOT called
        self.stream_manager.on_challenge_started.assert_not_called()

    @patch("services.poller.helper")
    @patch("services.poller.evaluate_timer_transition")
    @patch("time.time")
    def test_stream_suppressed_on_abnormal_low_time(self, mock_time, mock_evaluate, mock_helper):
        """Verify on_challenge_started NOT called when time_remaining < 3500."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = True

        m3u8_url = "http://angelcam.example.com/playlist.m3u8"
        self.angelcam.get_m3u8.return_value = (m3u8_url, False)
        self.angelcam.download_video.return_value = ("/tmp/video.mp4", False)
        self.pipeline.get_frames.return_value = ["3000", "6000", "6000", "6000", "6000", "6000"]

        # Only timer 0 triggers an alert, others return no-change transitions
        alert_transition = MagicMock()
        alert_transition.case = CASE_IDLE_TRIGGER
        alert_transition.ignored_low_value = False
        alert_transition.alert_event = MagicMock(timer_position=1, time_remaining=3000)
        alert_transition.timer_state = TimerState(tracked_time=3000, has_alerted=True, last_reset_time=0)

        idle_transition = MagicMock()
        idle_transition.case = CASE_UNCHANGED
        idle_transition.ignored_low_value = False
        idle_transition.alert_event = None
        idle_transition.timer_state = TimerState(tracked_time=6000, has_alerted=False, last_reset_time=0)

        # First call (timer 0) alerts, rest are idle
        mock_evaluate.side_effect = [alert_transition] + [idle_transition] * 5

        # Run poller
        run_once(
            first=False,
            daily_challenge_count=0,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify stream_manager.on_challenge_started was NOT called (alert suppressed)
        self.stream_manager.on_challenge_started.assert_not_called()

    @patch("services.poller.helper")
    @patch("services.poller.evaluate_timer_transition")
    @patch("time.time")
    def test_stream_suppressed_on_50_minute_timer(self, mock_time, mock_evaluate, mock_helper):
        """Verify on_challenge_started NOT called when time_remaining == 5000 (50:00)."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = True

        m3u8_url = "http://angelcam.example.com/playlist.m3u8"
        self.angelcam.get_m3u8.return_value = (m3u8_url, False)
        self.angelcam.download_video.return_value = ("/tmp/video.mp4", False)
        self.pipeline.get_frames.return_value = ["5000", "6000", "6000", "6000", "6000", "6000"]

        # Only timer 0 triggers an alert, others return no-change transitions
        alert_transition = MagicMock()
        alert_transition.case = CASE_IDLE_TRIGGER
        alert_transition.ignored_low_value = False
        alert_transition.alert_event = MagicMock(timer_position=1, time_remaining=5000)
        alert_transition.timer_state = TimerState(tracked_time=5000, has_alerted=True, last_reset_time=0)

        idle_transition = MagicMock()
        idle_transition.case = CASE_UNCHANGED
        idle_transition.ignored_low_value = False
        idle_transition.alert_event = None
        idle_transition.timer_state = TimerState(tracked_time=6000, has_alerted=False, last_reset_time=0)

        # First call (timer 0) alerts, rest are idle
        mock_evaluate.side_effect = [alert_transition] + [idle_transition] * 5

        # Run poller
        run_once(
            first=False,
            daily_challenge_count=0,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify stream NOT triggered (50:00 is filtered out)
        self.stream_manager.on_challenge_started.assert_not_called()

    @patch("services.poller.helper")
    @patch("time.time")
    def test_closed_hours_tick_with_shorter_poll_when_streaming(self, mock_time, mock_helper):
        """Verify tick(now) called and shorter poll interval when streaming during closed hours."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = False  # Closed
        mock_helper.getTime.return_value = "03:00:00"

        # Stream is currently active
        self.stream_manager.is_streaming = True

        # Run poller
        _, sleep_time = run_once(
            first=False,
            daily_challenge_count=5,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify tick was called with current timestamp
        self.stream_manager.tick.assert_called_once_with(1234567890)

        # Verify shorter poll interval (30-60s range)
        self.assertGreaterEqual(sleep_time, 30)
        self.assertLessEqual(sleep_time, 60)

    @patch("services.poller.helper")
    @patch("time.time")
    def test_closed_hours_tick_with_longer_poll_when_not_streaming(self, mock_time, mock_helper):
        """Verify tick(now) called and longer poll interval when NOT streaming during closed hours."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = False  # Closed
        mock_helper.getTime.return_value = "03:00:00"

        # Stream is NOT active
        self.stream_manager.is_streaming = False

        # Run poller
        _, sleep_time = run_once(
            first=False,
            daily_challenge_count=5,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify tick was called
        self.stream_manager.tick.assert_called_once_with(1234567890)

        # Verify longer poll interval (300-600s range)
        self.assertGreaterEqual(sleep_time, 300)
        self.assertLessEqual(sleep_time, 600)

    @patch("services.poller.helper")
    @patch("services.poller.evaluate_timer_transition")
    @patch("time.time")
    def test_discord_message_contains_both_urls(self, mock_time, mock_evaluate, mock_helper):
        """Verify Discord message receives both angelcam_url and youtube_stream_url."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = True
        mock_helper.getDateTime.return_value = "2024-01-15 12:00:00"

        m3u8_url = "http://angelcam.example.com/playlist.m3u8"
        self.angelcam.get_m3u8.return_value = (m3u8_url, False)
        self.angelcam.download_video.return_value = ("/tmp/video.mp4", False)
        self.pipeline.get_frames.return_value = ["6000", "6000", "6000", "6000", "6000", "6000"]

        # Only timer 0 triggers an alert, others return no-change transitions
        alert_transition = MagicMock()
        alert_transition.case = CASE_IDLE_TRIGGER
        alert_transition.ignored_low_value = False
        alert_transition.alert_event = MagicMock(timer_position=1, time_remaining=6000)
        alert_transition.timer_state = TimerState(tracked_time=6000, has_alerted=True, last_reset_time=0)

        idle_transition = MagicMock()
        idle_transition.case = CASE_UNCHANGED
        idle_transition.ignored_low_value = False
        idle_transition.alert_event = None
        idle_transition.timer_state = TimerState(tracked_time=6000, has_alerted=False, last_reset_time=0)

        # First call (timer 0) alerts, rest are idle
        mock_evaluate.side_effect = [alert_transition] + [idle_transition] * 5

        # Run poller
        run_once(
            first=False,
            daily_challenge_count=0,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify Discord notifier called with both URLs
        self.notifier.send_message.assert_called_once_with(
            False,
            1,
            6000,
            "http://angelcam.example.com/stream",
            "2024-01-15 12:00:00",
            youtube_stream_url="https://youtube.com/watch?v=test",
        )

    @patch("services.poller.helper")
    @patch("services.poller.evaluate_timer_transition")
    @patch("time.time")
    def test_discord_message_youtube_url_none_when_streaming_disabled(self, mock_time, mock_evaluate, mock_helper):
        """Verify youtube_stream_url is None when streaming disabled."""
        mock_time.return_value = 1234567890.0
        mock_helper.withinTimePeriod.return_value = True
        mock_helper.getDateTime.return_value = "2024-01-15 12:00:00"

        # Disable streaming
        self.settings.streaming_enabled = False

        m3u8_url = "http://angelcam.example.com/playlist.m3u8"
        self.angelcam.get_m3u8.return_value = (m3u8_url, False)
        self.angelcam.download_video.return_value = ("/tmp/video.mp4", False)
        self.pipeline.get_frames.return_value = ["6000", "6000", "6000", "6000", "6000", "6000"]

        # Only timer 0 triggers an alert, others return no-change transitions
        alert_transition = MagicMock()
        alert_transition.case = CASE_IDLE_TRIGGER
        alert_transition.ignored_low_value = False
        alert_transition.alert_event = MagicMock(timer_position=1, time_remaining=6000)
        alert_transition.timer_state = TimerState(tracked_time=6000, has_alerted=True, last_reset_time=0)

        idle_transition = MagicMock()
        idle_transition.case = CASE_UNCHANGED
        idle_transition.ignored_low_value = False
        idle_transition.alert_event = None
        idle_transition.timer_state = TimerState(tracked_time=6000, has_alerted=False, last_reset_time=0)

        # First call (timer 0) alerts, rest are idle
        mock_evaluate.side_effect = [alert_transition] + [idle_transition] * 5

        # Run poller
        run_once(
            first=False,
            daily_challenge_count=0,
            settings=self.settings,
            state=self.state,
            angelcam=self.angelcam,
            pipeline=self.pipeline,
            notifier=self.notifier,
            stream_manager=self.stream_manager,
        )

        # Verify youtube_stream_url is None
        self.notifier.send_message.assert_called_once_with(
            False,
            1,
            6000,
            "http://angelcam.example.com/stream",
            "2024-01-15 12:00:00",
            youtube_stream_url=None,
        )


if __name__ == "__main__":
    unittest.main()

