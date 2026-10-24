"""Loads, migrates, and exposes read-only configuration values."""

import json
import time

import helper
from config import CONFIG_FILE, DEFAULT_TIMEZONE, DEFAULT_VIDEO_URL


class SettingsStore:
    """Immutable view of the user-managed settings in ``config.json``.

    On construction the config file is loaded and any missing keys are
    migrated in-place (absorbing the old ``migrations.py`` logic).
    """

    def __init__(self, config_path: str = CONFIG_FILE):
        self._path = config_path
        self._data = self._load_and_migrate()

    # -- public properties ---------------------------------------------------

    @property
    def timezone(self) -> str:
        return self._data.get("timezone", DEFAULT_TIMEZONE)

    @property
    def video_url(self) -> str:
        return self._data.get("videoUrl", DEFAULT_VIDEO_URL)

    @property
    def should_send_wrapup(self) -> bool:
        return self._data.get("shouldSendWrapup", False)

    @property
    def ocr_engine_args(self) -> dict:
        return self._data["ocrEngine"]["args"]

    @property
    def filter_config(self) -> dict:
        return self._data["ocrEngine"].get("filters", {})

    @property
    def discord_config(self) -> dict:
        return self._data["discord"]

    # -- migration -----------------------------------------------------------

    def _load_and_migrate(self) -> dict:
        """Load config.json and apply any missing-key migrations."""
        with open(self._path, "r") as f:
            data = json.load(f)

        dirty = False

        # timers — list of 6 timer tuples
        if "timers" not in data or len(data.get("timers", [])) != 6:
            run_time = int(time.time())
            data["timers"] = [
                (6000, False, run_time),
                (6000, False, run_time),
                (6000, False, run_time),
                (6000, False, run_time),
                (6000, False, run_time),
                (6000, False, run_time),
            ]
            dirty = True
            helper.logmessage("migration - tracking of timers has been added to the config file.")

        # shouldSendWrapup
        if "shouldSendWrapup" not in data or data["shouldSendWrapup"] is None:
            data["shouldSendWrapup"] = False
            dirty = True
            helper.logmessage(
                "migration - shouldSendWrapup defaulted to false. "
                "Please update the config to enable the end of day wrapup feature."
            )

        # videoUrl
        if "videoUrl" not in data or data["videoUrl"] is None:
            data["videoUrl"] = DEFAULT_VIDEO_URL
            dirty = True
            helper.logmessage(f"migration - videoUrl defaulted to {DEFAULT_VIDEO_URL}.")

        # ocrEngine.filters
        if "filters" not in data.get("ocrEngine", {}) or data["ocrEngine"]["filters"] is None:
            data["ocrEngine"]["filters"] = {
                "clock1": False,
                "clock2": False,
                "clock3": False,
                "clock4": False,
                "clock5": False,
                "clock6": False,
            }
            dirty = True
            helper.logmessage("migration - filters defaulted to false for all timers.")

        # timezone (new field)
        if "timezone" not in data:
            data["timezone"] = DEFAULT_TIMEZONE
            dirty = True
            helper.logmessage(f"migration - timezone defaulted to {DEFAULT_TIMEZONE}.")

        # streaming section
        if "streaming" not in data:
            data["streaming"] = {
                "enabled": False,
                "rtmpUrl": config.DEFAULT_RTMP_URL,
                "streamKey": "",
                "publicStreamUrl": "",
                "durationMinutes": 70,
                "audioMode": config.DEFAULT_AUDIO_MODE,
            }
            dirty = True
            helper.logmessage("migration - streaming section added with defaults.")

        if dirty:
            self._save(data)

        return data

    def _save(self, data: dict) -> None:
        """Write config data back to disk (used only during migration)."""
        with open(self._path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()

    @property
    def streaming_enabled(self) -> bool:
        return self._data.get("streaming", {}).get("enabled", False)

    @property
    def rtmp_url(self) -> str:
        return self._data.get("streaming", {}).get("rtmpUrl", config.DEFAULT_RTMP_URL)

    @property
    def stream_key(self) -> str:
        return self._data.get("streaming", {}).get("streamKey", "")

    @property
    def public_stream_url(self) -> str | None:
        url = self._data.get("streaming", {}).get("publicStreamUrl", "")
        return url if url else None

    @property
    def stream_duration_seconds(self) -> int:
        minutes = self._data.get("streaming", {}).get("durationMinutes", 70)
        return minutes * 60

    @property
    def stream_audio_mode(self) -> str:
        return self._data.get("streaming", {}).get("audioMode", config.DEFAULT_AUDIO_MODE)

    @property
    def stream_destination(self) -> str | None:
        """Returns rtmp://url/streamKey if stream_key exists, else None"""
        key = self.stream_key
        if not key:
            return None
        return f"{self.rtmp_url}/{key}"
