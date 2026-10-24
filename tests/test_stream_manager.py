"""Unit tests for StreamManager."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from services.stream_manager import StreamManager
from storage.settings_store import SettingsStore


class TestStreamManager(unittest.TestCase):
    """Test StreamManager streaming lifecycle."""

    def test_streaming_disabled(self):
        """No process spawned when streaming disabled."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = False

        mock_popen = MagicMock()
        manager = StreamManager(settings, popen_fn=mock_popen)

        result = manager.on_challenge_started("http://test.m3u8", 1000)

        self.assertFalse(result)
        mock_popen.assert_not_called()

    def test_missing_stream_key(self):
        """No process spawned when stream_destination returns None."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = None

        mock_popen = MagicMock()
        manager = StreamManager(settings, popen_fn=mock_popen)

        result = manager.on_challenge_started("http://test.m3u8", 1000)

        self.assertFalse(result)
        mock_popen.assert_not_called()

    @patch("helper.logmessage")
    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_initial_stream_start(self, mock_open, mock_path, mock_log):
        """Verify FFmpeg command structure on initial stream start."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200
        settings.stream_audio_mode = "passthrough"

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen = MagicMock(return_value=mock_process)

        manager = StreamManager(settings, popen_fn=mock_popen)

        result = manager.on_challenge_started("http://test.m3u8", 1000)

        self.assertTrue(result)
        self.assertTrue(manager.is_streaming)
        self.assertEqual(manager.stream_end_time, 1000 + 4200)

        # Verify FFmpeg was called
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]

        # Check key flags
        self.assertIn("ffmpeg", cmd)
        self.assertIn("-re", cmd)
        self.assertIn("-headers", cmd)
        self.assertIn("http://test.m3u8", cmd)
        self.assertIn("rtmp://youtube.com/live2/test-key", cmd)
        self.assertIn("-c:v", cmd)
        self.assertIn("copy", cmd)

    @patch("helper.logmessage")
    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_stream_extension(self, mock_open, mock_path, mock_log):
        """Verify end_time = max(current, now + 4200) on second challenge."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200
        settings.stream_audio_mode = "passthrough"

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen = MagicMock(return_value=mock_process)

        manager = StreamManager(settings, popen_fn=mock_popen)

        # Start initial stream at t=1000
        manager.on_challenge_started("http://test.m3u8", 1000)
        self.assertEqual(manager.stream_end_time, 1000 + 4200)  # 5200

        # Second challenge at t=3000 (within stream window)
        result = manager.on_challenge_started("http://test.m3u8", 3000)
        self.assertTrue(result)
        # end_time = max(5200, 3000 + 4200) = max(5200, 7200) = 7200
        self.assertEqual(manager.stream_end_time, 7200)

        # Verify FFmpeg was only called once
        self.assertEqual(mock_popen.call_count, 1)

    @patch("helper.logmessage")
    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_auto_stop_via_tick(self, mock_open, mock_path, mock_log):
        """Verify clean shutdown when duration expires."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200
        settings.stream_audio_mode = "passthrough"

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll = MagicMock(return_value=None)  # Still running
        mock_popen = MagicMock(return_value=mock_process)

        manager = StreamManager(settings, popen_fn=mock_popen)

        # Start stream at t=1000, ends at t=5200
        manager.on_challenge_started("http://test.m3u8", 1000)

        # Tick before end time
        manager.tick(5000)
        self.assertTrue(manager.is_streaming)
        mock_process.terminate.assert_not_called()

        # Tick at end time
        manager.tick(5200)
        self.assertFalse(manager.is_streaming)
        mock_process.terminate.assert_called_once()

    @patch("helper.logmessage")
    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_graceful_shutdown(self, mock_open, mock_path, mock_log):
        """Verify SIGTERM, 5s timeout, SIGKILL."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200
        settings.stream_audio_mode = "passthrough"

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll = MagicMock(return_value=None)
        # First wait(timeout=5) raises TimeoutExpired, second wait() succeeds
        mock_process.wait = MagicMock(side_effect=[subprocess.TimeoutExpired("ffmpeg", 5), None])
        mock_popen = MagicMock(return_value=mock_process)

        manager = StreamManager(settings, popen_fn=mock_popen)
        manager.on_challenge_started("http://test.m3u8", 1000)

        # Stop stream
        manager.stop_stream("test")

        # Verify SIGTERM then SIGKILL
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_unexpected_process_exit(self, mock_open, mock_path):
        """Logs error and resets state when FFmpeg exits unexpectedly."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200
        settings.stream_audio_mode = "passthrough"

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll = MagicMock(return_value=1)  # Exited with code 1
        mock_process.returncode = 1
        mock_popen = MagicMock(return_value=mock_process)

        manager = StreamManager(settings, popen_fn=mock_popen)
        manager.on_challenge_started("http://test.m3u8", 1000)

        # Tick detects unexpected exit
        manager.tick(2000)
        self.assertFalse(manager.is_streaming)
        self.assertIsNone(manager.stream_end_time)

    @patch("helper.logmessage")
    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_audio_mode_variants(self, mock_open, mock_path, mock_log):
        """Verify commands for silent, passthrough, none."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200

        mock_process = MagicMock()
        mock_popen = MagicMock(return_value=mock_process)

        # Test passthrough mode
        settings.stream_audio_mode = "passthrough"
        manager = StreamManager(settings, popen_fn=mock_popen)
        manager.on_challenge_started("http://test.m3u8", 1000)
        cmd = mock_popen.call_args[0][0]
        self.assertIn("-c:a", cmd)
        self.assertIn("aac", cmd)
        self.assertIn("-ar", cmd)
        self.assertIn("44100", cmd)

        # Test silent mode
        settings.stream_audio_mode = "silent"
        manager = StreamManager(settings, popen_fn=mock_popen)
        manager.on_challenge_started("http://test.m3u8", 2000)
        cmd = mock_popen.call_args[0][0]
        # anullsrc is part of the -i argument, not a standalone flag
        self.assertTrue(any("anullsrc" in arg for arg in cmd))
        self.assertIn("-shortest", cmd)

        # Test none mode
        settings.stream_audio_mode = "none"
        manager = StreamManager(settings, popen_fn=mock_popen)
        manager.on_challenge_started("http://test.m3u8", 3000)
        cmd = mock_popen.call_args[0][0]
        self.assertIn("-an", cmd)

    @patch("helper.logmessage")
    @patch("services.stream_manager.Path")
    @patch("builtins.open", new_callable=MagicMock)
    def test_ffmpeg_headers_format(self, mock_open, mock_path, mock_log):
        """Verify single -headers flag with CRLF-separated values."""
        settings = MagicMock(spec=SettingsStore)
        settings.streaming_enabled = True
        settings.stream_destination = "rtmp://youtube.com/live2/test-key"
        settings.stream_duration_seconds = 4200
        settings.stream_audio_mode = "passthrough"

        mock_process = MagicMock()
        mock_popen = MagicMock(return_value=mock_process)

        manager = StreamManager(settings, popen_fn=mock_popen)
        manager.on_challenge_started("http://test.m3u8", 1000)

        cmd = mock_popen.call_args[0][0]

        # Find -headers flag
        headers_idx = cmd.index("-headers")
        headers_value = cmd[headers_idx + 1]

        # Verify it's a single string with CRLF separators
        self.assertIsInstance(headers_value, str)
        self.assertIn("\r\n", headers_value)

        # Count occurrences of -headers flag (should be exactly 1)
        headers_count = cmd.count("-headers")
        self.assertEqual(headers_count, 1, "Should have exactly one -headers flag")


if __name__ == "__main__":
    unittest.main()
