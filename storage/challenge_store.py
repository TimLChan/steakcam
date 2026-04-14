"""SQLite-backed store for daily steak challenge counts."""

import sqlite3
from datetime import datetime, timezone

import pytz


class ChallengeStore:
    """Persists the number of steak challenges completed per calendar day.

    The date is stored as an ISO-format string (``YYYY-MM-DD``) localised to
    the timezone passed by the caller (typically ``US/Central``).  The
    ``date`` column is the PRIMARY KEY, which also serves as the index
    required by the acceptance criteria.
    """

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS daily_challenges (
            date  TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        );
    """

    def __init__(self, db_path: str) -> None:
        """Open (or create) *db_path* and ensure the table exists."""
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(self._CREATE_TABLE)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _today(self, tz_name: str) -> str:
        """Return today's date as ``YYYY-MM-DD`` in *tz_name*."""
        tz = pytz.timezone(tz_name)
        return datetime.now(tz=timezone.utc).astimezone(tz).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_today_count(self, tz_name: str) -> int:
        """Return the challenge count for today, or ``0`` if no row exists."""
        date = self._today(tz_name)
        row = self._conn.execute(
            "SELECT count FROM daily_challenges WHERE date = ?", (date,)
        ).fetchone()
        return row[0] if row else 0

    def increment_today(self, tz_name: str) -> None:
        """Atomically increment today's count, creating the row if needed."""
        date = self._today(tz_name)
        self._conn.execute(
            """
            INSERT INTO daily_challenges (date, count) VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET count = count + 1
            """,
            (date,),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()
