"""Manages FFmpeg streaming lifecycle for YouTube Live."""

import subprocess
import time
from datetime import datetime
from pathlib import Path

import config
import helper
from storage.settings_store import SettingsStore


class StreamManager:
    """Manages FFmpeg subprocess for YouTube Live streaming."""

    def __init__(self, settings: SettingsStore, popen_fn=subprocess.Popen):
        self._settings = settings
        self._popen_fn = popen_fn  # allows mocking in tests
        self._process = None
        self._stream_end_time = None
        self._log_file = None

    @property
    def is_streaming(self) -> bool:
        return self._process is not None

    @property
    def stream_end_time(self) -> int | None:
        return self._stream_end_time

    def on_challenge_started(self, m3u8_url: str, now: int) -> bool:
        """Start or extend stream when challenge detected.

        Args:
            m3u8_url: AngelCam HLS playlist URL
            now: Current Unix timestamp

        Returns:
            True if action taken, False otherwise
        """
        if not self._settings.streaming_enabled:
            return False

        destination = self._settings.stream_destination
        if not destination:
            helper.logmessage("stream_manager: stream_key not configured, skipping stream")
            return False

        duration = self._settings.stream_duration_seconds

        # Already streaming: extend end time
        if self.is_streaming:
            old_end = self._stream_end_time
            self._stream_end_time = max(self._stream_end_time, now + duration)
            helper.logmessage(
                f"stream_manager: extended stream end time from "
                f"{datetime.fromtimestamp(old_end)} to {datetime.fromtimestamp(self._stream_end_time)}"
            )
            return True

        # Start new stream
        self._stream_end_time = now + duration
        cmd = self._build_ffmpeg_command(m3u8_url)

        # Prepare log file
        # WARNING: FFmpeg logs contain the full RTMP URL with stream key
        # Treat files in logs/streaming/ as sensitive
        log_dir = Path("logs/streaming")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_file = log_dir / f"ffmpeg_{timestamp}.log"

        try:
            with open(self._log_file, "w") as log_f:
                self._process = self._popen_fn(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                )
            helper.logmessage(
                f"stream_manager: started stream, end time {datetime.fromtimestamp(self._stream_end_time)}, "
                f"pid {self._process.pid}, log {self._log_file}"
            )
            return True
        except Exception as e:
            helper.logmessage(f"stream_manager: failed to start FFmpeg: {e}")
            self._process = None
            self._stream_end_time = None
            return False

    def _build_ffmpeg_command(self, m3u8_url: str) -> list[str]:
        """Build FFmpeg command arguments.

        Args:
            m3u8_url: AngelCam HLS playlist URL

        Returns:
            List of command arguments
        """
        destination = self._settings.stream_destination
        audio_mode = self._settings.stream_audio_mode

        # Format headers as single CRLF-separated string
        header_str = "\r\n".join([f"{k}: {v}" for k, v in config.HEADERS.items()])

        cmd = [
            "ffmpeg",
            "-re",  # Read at native frame rate
            "-headers", header_str,  # AngelCam authentication
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", m3u8_url,
        ]

        # Add synthetic audio input for silent mode
        if audio_mode == "silent":
            cmd.extend([
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            ])

        # Audio handling
        if audio_mode == "passthrough":
            # Transcode 8kHz mono → 44.1kHz stereo
            # Explicitly map video stream 0 and audio stream 0
            cmd.extend([
                "-map", "0:v:0",  # First video stream
                "-map", "0:a:0",  # First audio stream
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
            ])
        elif audio_mode == "silent":
            # Use synthetic silent audio from input 1
            cmd.extend([
                "-map", "0:v:0",  # Video from input 0
                "-map", "1:a:0",  # Audio from input 1 (anullsrc)
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",  # Stop when video ends
            ])
        elif audio_mode == "none":
            # No audio (YouTube will reject, testing only)
            cmd.extend([
                "-map", "0:v:0",  # First video stream
                "-c:v", "copy",
                "-an"
            ])
        else:
            # Unknown mode: default to passthrough
            helper.logmessage(f"stream_manager: unknown audioMode '{audio_mode}', defaulting to passthrough")
            cmd.extend([
                "-map", "0:v:0",
                "-map", "0:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
            ])

        # Streaming output
        cmd.extend([
            "-f", "flv",
            destination,
        ])

        return cmd

    def tick(self, now: int) -> None:
        """Called every poll cycle to check if stream should stop.

        Args:
            now: Current Unix timestamp
        """
        if not self.is_streaming:
            return

        # Check if process exited unexpectedly
        if self._process.poll() is not None:
            exit_code = self._process.returncode
            helper.logmessage(f"stream_manager: FFmpeg exited unexpectedly with code {exit_code}")
            self._process = None
            self._stream_end_time = None
            self._log_file = None
            return

        # Check if duration expired
        if now >= self._stream_end_time:
            self.stop_stream("duration expired")

    def stop_stream(self, reason: str = "stopped") -> None:
        """Stop FFmpeg process gracefully.

        Args:
            reason: Reason for stopping (for logging)
        """
        if not self.is_streaming:
            return

        helper.logmessage(f"stream_manager: stopping stream, reason: {reason}")

        # SIGTERM for graceful shutdown
        self._process.terminate()

        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # SIGKILL if still running after 5 seconds
            helper.logmessage("stream_manager: FFmpeg did not terminate gracefully, sending SIGKILL")
            self._process.kill()
            self._process.wait()

        helper.logmessage(f"stream_manager: stream stopped, final log at {self._log_file}")
        self._process = None
        self._stream_end_time = None
        self._log_file = None
