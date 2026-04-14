"""Manages mutable runtime state (tracked timers, daily counters)."""

import json

from config import CONFIG_FILE, DB_FILE
from storage.challenge_store import ChallengeStore


class StateStore:
    """Reads and writes the mutable ``timers`` section of ``config.json``.

    Keeps timer state in memory and persists on :meth:`save`.
    Also owns a :class:`ChallengeStore` for SQLite-backed daily challenge counts.
    """

    def __init__(self, config_path: str = CONFIG_FILE, db_path: str = DB_FILE):
        self._path = config_path
        self.wrapup_sent_today = False
        self.challenges = ChallengeStore(db_path)
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
