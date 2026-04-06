"""Manages mutable runtime state (tracked timers, daily counters)."""

import json

from config import CONFIG_FILE


class StateStore:
    """Reads and writes the mutable ``timers`` section of ``config.json``.

    Keeps timer state in memory and persists on :meth:`save`.
    """

    def __init__(self, config_path: str = CONFIG_FILE):
        self._path = config_path
        self.daily_challenge_count = 0
        self.wrapup_sent_today = False
        self._load()

    @property
    def tracked_timers(self) -> list:
        return self._timers

    def save(self) -> None:
        """Write current timer state back to config.json."""
        with open(self._path, "r") as f:
            data = json.load(f)

        data["timers"] = self._timers

        with open(self._path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def _load(self) -> None:
        """Read the timers list from config.json."""
        with open(self._path, "r") as f:
            data = json.load(f)
        self._timers = data["timers"]
