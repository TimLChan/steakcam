"""Tests for reporting winners: Discord payloads, poller wiring and the stale segment guard."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

import pytz

from clients.angelcam_client import AngelcamClient
from clients.discord_client import DiscordNotifier
from services.frame_pipeline import FramePipeline
from services.poller import run_once
from storage.settings_store import SettingsStore
from storage.state_store import StateStore

START = 1_000_000


def make_notifier():
    session = MagicMock()
    session.post.return_value.status_code = 204
    config = {
        "name": "steakbot",
        "avatar": "http://img",
        "webhooks": [{"name": "hook1", "url": "http://webhook"}],
    }
    return DiscordNotifier(config, session=session), session


def sent_payload(session):
    session.post.assert_called_once()
    return session.post.call_args.kwargs["json"]


class TestWrapupWinners(unittest.TestCase):

    def _wrapup_fields(self, challengers, win_count):
        notifier, session = make_notifier()
        dt = pytz.utc.localize(datetime(2026, 3, 1, 23, 50))
        datetime_mock = MagicMock()
        datetime_mock.now.return_value = dt
        with patch("clients.discord_client.datetime", datetime_mock), \
             patch("helper.datetime", datetime_mock), \
             patch("time.sleep"):
            notifier.send_wrapup(challengers, "UTC", False, win_count=win_count)
        return sent_payload(session)["embeds"][0]["fields"]

    def test_no_winners_field_when_flag_disabled(self):
        fields = self._wrapup_fields(10, None)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["value"], "10 challengers")

    def test_winners_field_with_percentage(self):
        fields = self._wrapup_fields(10, 1)
        self.assertEqual(fields[1]["name"], "winners (beta)")
        self.assertEqual(fields[1]["value"], "1 challenger (10%)")

    def test_percentage_is_rounded(self):
        fields = self._wrapup_fields(3, 1)
        self.assertEqual(fields[1]["value"], "1 challenger (33%)")

    def test_zero_challengers_omits_percentage(self):
        fields = self._wrapup_fields(0, 0)
        self.assertEqual(fields[0]["value"], "0 challengers")
        self.assertEqual(fields[1]["value"], "0 challengers")

    def test_single_challenger_is_singular(self):
        fields = self._wrapup_fields(1, 1)
        self.assertEqual(fields[0]["value"], "1 challenger")
        self.assertEqual(fields[1]["value"], "1 challenger (100%)")


class TestWinMessage(unittest.TestCase):

    def test_win_message_payload(self):
        notifier, session = make_notifier()
        with patch("time.sleep"):
            notifier.send_win_message(False, 3, 3221, "http://stream", "Oct 10 - 07:42:10 PM CDT")

        embed = sent_payload(session)["embeds"][0]
        self.assertEqual(embed["title"], "Steak Challenge Winner (beta)")
        values = {field["name"]: field["value"] for field in embed["fields"]}
        self.assertEqual(values["timer position (from left)"], "timer 3")
        self.assertEqual(values["time remaining"], "32:21")
        self.assertEqual(values["finished in"], "27:39")
        self.assertEqual(values["time @ the big texan"], "Oct 10 - 07:42:10 PM CDT")

    def test_win_message_handles_low_values(self):
        notifier, session = make_notifier()
        with patch("time.sleep"):
            notifier.send_win_message(False, 1, 45)

        values = {field["name"]: field["value"] for field in sent_payload(session)["embeds"][0]["fields"]}
        self.assertEqual(values["time remaining"], "00:45")
        self.assertEqual(values["finished in"], "59:15")

    def test_win_message_suppressed_on_first_poll(self):
        notifier, session = make_notifier()
        notifier.send_win_message(True, 3, 3221)
        session.post.assert_not_called()


class TestPollerWins(unittest.TestCase):

    def _run(self, readings, *, report_winners, record_win=True, tracked=None):
        settings = MagicMock(spec=SettingsStore)
        settings.timezone = "US/Central"
        settings.video_url = "http://stream"
        settings.should_send_wrapup = False
        settings.should_report_winners = report_winners

        state = MagicMock(spec=StateStore)
        state.wrapup_sent_today = False
        state.challenges = MagicMock()
        state.challenges.record_win.return_value = record_win
        if tracked is None:
            tracked = [[6000, False, START, False] for _ in range(6)]
            tracked[2] = [3221, True, START, False]
        state.tracked_timers = tracked

        angelcam = MagicMock()
        angelcam.get_m3u8.return_value = ("url", False)
        angelcam.download_video.return_value = ("file.ts", False)

        pipeline = MagicMock(spec=FramePipeline)
        pipeline.get_frames.return_value = readings

        notifier = MagicMock()

        with patch("helper.withinTimePeriod", return_value=True):
            run_once(
                first=False,
                daily_challenge_count=0,
                settings=settings,
                state=state,
                angelcam=angelcam,
                pipeline=pipeline,
                notifier=notifier,
            )
        return state, notifier

    def test_win_recorded_but_not_sent_when_flag_disabled(self):
        state, notifier = self._run(["6000", "6000", "3221", "6000", "6000", "6000"], report_winners=False)
        state.challenges.record_win.assert_called_once_with("US/Central", 3, 3221, START)
        notifier.send_win_message.assert_not_called()
        self.assertEqual(state.tracked_timers[2], (3221, True, START, True))

    def test_win_sent_when_flag_enabled(self):
        state, notifier = self._run(["6000", "6000", "3221", "6000", "6000", "6000"], report_winners=True)
        notifier.send_win_message.assert_called_once()
        args = notifier.send_win_message.call_args.args
        self.assertEqual(args[:4], (False, 3, 3221, "http://stream"))

    def test_duplicate_win_is_not_sent(self):
        _, notifier = self._run(["6000", "6000", "3221", "6000", "6000", "6000"], report_winners=True, record_win=False)
        notifier.send_win_message.assert_not_called()

    def test_blank_ocr_skips_the_poll_then_win_is_detected(self):
        tracked = [[6000, False, START, False] for _ in range(6)]
        tracked[2] = [3221, True, START, False]

        # One clock failed OCR, so only 5 readings come back and the whole poll is skipped
        state, _ = self._run(["6000", "6000", "6000", "6000", "6000"], report_winners=True, tracked=tracked)
        state.challenges.record_win.assert_not_called()
        self.assertEqual(tracked[2], [3221, True, START, False])

        state, notifier = self._run(["6000", "6000", "3221", "6000", "6000", "6000"], report_winners=True, tracked=tracked)
        state.challenges.record_win.assert_called_once()
        notifier.send_win_message.assert_called_once()


class TestPollerWrapupWinners(unittest.TestCase):

    def _close(self, report_winners):
        settings = MagicMock(spec=SettingsStore)
        settings.timezone = "US/Central"
        settings.should_send_wrapup = True
        settings.should_report_winners = report_winners

        state = MagicMock(spec=StateStore)
        state.wrapup_sent_today = False
        state.challenges = MagicMock()
        state.challenges.get_today_win_count.return_value = 2

        notifier = MagicMock()
        with patch("random.randint", return_value=1), \
             patch("helper.withinTimePeriod", return_value=False):
            run_once(
                first=False,
                daily_challenge_count=8,
                settings=settings,
                state=state,
                angelcam=MagicMock(),
                pipeline=MagicMock(),
                notifier=notifier,
            )
        return notifier

    def test_wrapup_includes_win_count_when_enabled(self):
        notifier = self._close(True)
        notifier.send_wrapup.assert_called_once_with(8, "US/Central", False, win_count=2)

    def test_wrapup_omits_win_count_when_disabled(self):
        notifier = self._close(False)
        notifier.send_wrapup.assert_called_once_with(8, "US/Central", False, win_count=None)


class TestStaleSegment(unittest.TestCase):

    def _response(self, text="", content=b""):
        response = MagicMock()
        response.status_code = 200
        response.text = text
        response.content = content
        return response

    def _download(self, client, session, content):
        session.get.side_effect = [
            self._response(text="segment_1.ts\n"),
            self._response(content=content),
        ]
        file_open = mock_open()
        with patch("builtins.open", file_open):
            result = client.download_video("http://cdn/playlist.m3u8")
        return result, file_open

    def test_same_segment_twice_is_skipped(self):
        session = MagicMock()
        client = AngelcamClient(session)

        result, file_open = self._download(client, session, b"segment-bytes")
        self.assertEqual(result, ("video.ts", False))
        file_open.assert_called_once()

        result, file_open = self._download(client, session, b"segment-bytes")
        self.assertEqual(result, ("video.ts", True))
        file_open.assert_not_called()

    def test_new_segment_is_downloaded(self):
        session = MagicMock()
        client = AngelcamClient(session)

        self._download(client, session, b"segment-1")
        result, file_open = self._download(client, session, b"segment-2")
        self.assertEqual(result, ("video.ts", False))
        file_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
