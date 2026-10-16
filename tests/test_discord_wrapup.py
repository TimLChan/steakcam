import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime
import pytz
import time
import tempfile
import os

import helper
from clients.discord_client import DiscordNotifier
from services.poller import run_once
from storage.settings_store import SettingsStore
from storage.state_store import StateStore

class TestDiscordWrapup(unittest.TestCase):
    def test_get_formatted_date_ordinal_suffixes(self):
        cases = [
            ("2026-03-01 12:00:00", "Sun 1st March 2026"),
            ("2026-03-02 12:00:00", "Mon 2nd March 2026"),
            ("2026-03-03 12:00:00", "Tue 3rd March 2026"),
            ("2026-03-04 12:00:00", "Wed 4th March 2026"),
            ("2026-03-11 12:00:00", "Wed 11th March 2026"),
            ("2026-03-12 12:00:00", "Thu 12th March 2026"),
            ("2026-03-13 12:00:00", "Fri 13th March 2026"),
            ("2026-03-21 12:00:00", "Sat 21st March 2026"),
        ]
        for dt_str, expected in cases:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            # Create a mock datetime object that behaves like helper.datetime
            datetime_mock = MagicMock()
            datetime_mock.now.return_value = pytz.utc.localize(dt)
            with patch('helper.datetime', datetime_mock):
                self.assertEqual(helper.getFormattedDate("UTC"), expected)

    def test_discord_notifier_payload(self):
        session_mock = MagicMock()
        post_resp = MagicMock()
        post_resp.status_code = 204
        session_mock.post.return_value = post_resp
        
        config = {
            "name": "steakbot",
            "avatar": "http://img",
            "webhooks": [{"name": "hook1", "url": "http://webhook"}]
        }
        notifier = DiscordNotifier(config, session=session_mock)
        
        dt = pytz.utc.localize(datetime.strptime("2026-03-01 23:05:00", "%Y-%m-%d %H:%M:%S"))
        datetime_mock = MagicMock()
        datetime_mock.now.return_value = dt

        with patch('clients.discord_client.datetime', datetime_mock), \
             patch('helper.datetime', datetime_mock), \
             patch('time.sleep'):
            
            notifier.send_wrapup(5, "UTC", False)
            
            session_mock.post.assert_called_once()
            args, kwargs = session_mock.post.call_args
            self.assertEqual(args[0], "http://webhook")
            
            payload = kwargs["json"]
            self.assertEqual(payload["username"], "steakbot")
            self.assertEqual(payload["embeds"][0]["title"], "Steak Challenge Wrapup for Sun 1st March 2026")
            self.assertEqual(payload["embeds"][0]["fields"][0]["value"], "5 challengers")

    def test_poller_wrapup_trigger_and_reset(self):
        settings = MagicMock(spec=SettingsStore)
        settings.timezone = "UTC"
        settings.should_send_wrapup = True
        settings.should_report_winners = False
        
        state = MagicMock(spec=StateStore)
        state.wrapup_sent_today = False
        state.challenges = MagicMock()
        
        angelcam = MagicMock()
        pipeline = MagicMock()
        notifier = MagicMock()

        with patch('random.randint', return_value=1), \
             patch('helper.withinTimePeriod', return_value=False):
            
            # 1. Simulate close interval, should send wrapup
            daily_count, sleep_time = run_once(
                first=False,
                daily_challenge_count=3,
                settings=settings,
                state=state,
                angelcam=angelcam,
                pipeline=pipeline,
                notifier=notifier
            )
            
            notifier.send_wrapup.assert_called_once_with(3, "UTC", False, win_count=None)
            self.assertTrue(state.wrapup_sent_today)
            self.assertEqual(daily_count, 0)
            
            # 2. Simulate next poll interval, still closed. Shouldn't send again.
            notifier.send_wrapup.reset_mock()
            
            daily_count, sleep_time = run_once(
                first=False,
                daily_challenge_count=0,
                settings=settings,
                state=state,
                angelcam=angelcam,
                pipeline=pipeline,
                notifier=notifier
            )
            
            notifier.send_wrapup.assert_not_called()
            self.assertTrue(state.wrapup_sent_today)

        # 3. Simulate restaurant opening. Should reset wrapup_sent_today flag
        with patch('helper.withinTimePeriod', return_value=True):
            angelcam.get_m3u8.return_value = ("url", True) # skip processing
            
            run_once(
                first=False,
                daily_challenge_count=0,
                settings=settings,
                state=state,
                angelcam=angelcam,
                pipeline=pipeline,
                notifier=notifier
            )
            
            self.assertFalse(state.wrapup_sent_today)

    def test_poller_increment_persists_to_db(self):
        """A challenge alert causes state.challenges.increment_today to be called."""
        settings = MagicMock(spec=SettingsStore)
        settings.timezone = "US/Central"
        settings.should_send_wrapup = False
        settings.should_report_winners = False

        state = MagicMock(spec=StateStore)
        state.wrapup_sent_today = False
        state.challenges = MagicMock()
        state.tracked_timers = [(0, False, 0)] * 6

        # Build a fake pipeline response that triggers an alert on timer 0
        from models import TimerState
        from services.timer_engine import CASE_IDLE_TRIGGER
        from services.frame_pipeline import FramePipeline

        alert_event = MagicMock()
        alert_event.time_remaining = 4000
        alert_event.timer_position = 0

        transition = MagicMock()
        transition.case = CASE_IDLE_TRIGGER
        transition.ignored_low_value = False
        transition.alert_event = alert_event
        transition.win_event = None
        transition.timer_state.to_legacy.return_value = {"state": "active", "timestamp": 1}

        angelcam = MagicMock()
        angelcam.get_m3u8.return_value = ("url", False)
        angelcam.download_video.return_value = ("file.ts", False)

        pipeline = MagicMock(spec=FramePipeline)
        # 6 timers, timer 0 triggers
        pipeline.get_frames.return_value = ["4000", "0", "0", "0", "0", "0"]

        notifier = MagicMock()

        with patch('helper.withinTimePeriod', return_value=True), \
             patch('services.poller.evaluate_timer_transition', return_value=transition), \
             patch('time.time', return_value=0):
            run_once(
                first=False,
                daily_challenge_count=0,
                settings=settings,
                state=state,
                angelcam=angelcam,
                pipeline=pipeline,
                notifier=notifier,
            )

        state.challenges.increment_today.assert_called_with("US/Central")

    def test_poller_day_boundary_reloads_from_db(self):
        """When the restaurant re-opens, daily_challenge_count is loaded from DB."""
        settings = MagicMock(spec=SettingsStore)
        settings.timezone = "US/Central"
        settings.should_send_wrapup = False
        settings.should_report_winners = False

        state = MagicMock(spec=StateStore)
        state.wrapup_sent_today = True  # overnight guard was set
        state.challenges = MagicMock()
        state.challenges.get_today_count.return_value = 7  # DB has 7 from earlier

        angelcam = MagicMock()
        angelcam.get_m3u8.return_value = ("url", True)  # skip video processing

        pipeline = MagicMock()
        notifier = MagicMock()

        with patch('helper.withinTimePeriod', return_value=True):
            count, _ = run_once(
                first=False,
                daily_challenge_count=0,
                settings=settings,
                state=state,
                angelcam=angelcam,
                pipeline=pipeline,
                notifier=notifier,
            )

        state.challenges.get_today_count.assert_called_once_with("US/Central")
        self.assertEqual(count, 7)


if __name__ == "__main__":
    unittest.main()
