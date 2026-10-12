"""SQLite-backed store for daily steak challenge counts and wins."""

import sqlite3
import time
from datetime import datetime, timezone

import pytz


class ChallengeStore:
    """Persists the number of steak challenges completed per calendar day,
    along with one row per detected win.

    The date is stored as an ISO-format string (``YYYY-MM-DD``) localised to
    the timezone passed by the caller (typically ``US/Central``).  The
    ``date`` column is the PRIMARY KEY, which also serves as the index
    required by the acceptance criteria.

    The schema is versioned with ``PRAGMA user_version``.  Each entry in
    ``_MIGRATIONS`` takes the database to the next version and is applied
    automatically on startup.  Statements must be idempotent so a partially
    applied migration can safely be re-run.
    """

    _MIGRATIONS = [
        # v1: daily challenge counter (issue #3)
        [
            """
            CREATE TABLE IF NOT EXISTS daily_challenges (
                date  TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            );
            """,
        ],
        # v2: one row per detected win (issue #5)
        [
            """
            CREATE TABLE IF NOT EXISTS challenge_wins (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                date                 TEXT    NOT NULL,
                timer_position       INTEGER NOT NULL,
                time_remaining       INTEGER NOT NULL,
                challenge_started_at INTEGER NOT NULL,
                won_at               INTEGER NOT NULL,
                UNIQUE (timer_position, challenge_started_at)
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_challenge_wins_date ON challenge_wins(date);",
        ],
    ]

    def __init__(self, db_path: str) -> None:
        """Open (or create) *db_path* and apply any pending migrations."""
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._migrate()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        """Bring the schema up to the latest version."""
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for target, statements in enumerate(self._MIGRATIONS[version:], start=version + 1):
            for statement in statements:
                self._conn.execute(statement)
            self._conn.execute(f"PRAGMA user_version = {target}")
            self._conn.commit()

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

    def record_win(self, tz_name: str, timer_position: int, time_remaining: int, challenge_started_at: int) -> bool:
        """Record a win for today.

        Returns ``True`` if a new row was inserted, or ``False`` if this
        challenge (timer + start time) already has a win recorded.
        """
        date = self._today(tz_name)
        cursor = self._conn.execute(
            """
            INSERT OR IGNORE INTO challenge_wins
                (date, timer_position, time_remaining, challenge_started_at, won_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, timer_position, time_remaining, challenge_started_at, int(time.time())),
        )
        self._conn.commit()
        return cursor.rowcount == 1

    def get_today_win_count(self, tz_name: str) -> int:
        """Return the number of wins recorded for today."""
        date = self._today(tz_name)
        row = self._conn.execute(
            "SELECT COUNT(*) FROM challenge_wins WHERE date = ?", (date,)
        ).fetchone()
        return row[0]

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()
