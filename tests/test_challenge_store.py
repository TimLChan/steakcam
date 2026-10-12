"""Unit tests for ChallengeStore."""

import tempfile
import os
import sqlite3
import unittest
from datetime import date

from storage.challenge_store import ChallengeStore


# Fixed date strings used across tests so we're not time-sensitive
TODAY = date.today().strftime("%Y-%m-%d")
TOMORROW = date.fromordinal(date.today().toordinal() + 1).strftime("%Y-%m-%d")


class TestChallengeStore(unittest.TestCase):

    def _make_store(self, path: str) -> ChallengeStore:
        return ChallengeStore(path)

    def setUp(self):
        # Each test gets its own temp file so they're fully isolated
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = self._make_store(self._tmp.name)

    def tearDown(self):
        self.store.close()
        os.unlink(self._tmp.name)

    # ------------------------------------------------------------------
    # get_today_count
    # ------------------------------------------------------------------

    def test_get_today_count_returns_zero_when_no_row(self):
        """Fresh DB returns 0 — AC: initialised at 0 if no row for current date."""
        self.assertEqual(self.store.get_today_count("US/Central"), 0)

    def test_get_today_count_returns_persisted_value(self):
        """After increment, get_today_count returns the updated count."""
        self.store.increment_today("US/Central")
        self.store.increment_today("US/Central")
        self.assertEqual(self.store.get_today_count("US/Central"), 2)

    # ------------------------------------------------------------------
    # increment_today
    # ------------------------------------------------------------------

    def test_increment_today_creates_row(self):
        """First increment inserts a row with count = 1."""
        self.store.increment_today("US/Central")
        self.assertEqual(self.store.get_today_count("US/Central"), 1)

    def test_increment_today_increments_existing(self):
        """Second increment on the same date updates to count = 2."""
        self.store.increment_today("US/Central")
        self.store.increment_today("US/Central")
        self.assertEqual(self.store.get_today_count("US/Central"), 2)

    # ------------------------------------------------------------------
    # Independence between dates
    # ------------------------------------------------------------------

    def test_different_dates_are_independent(self):
        """Incrementing for a different date does not affect today's row."""
        # Directly insert a row for "tomorrow" by patching _today
        original_today = self.store._today

        self.store._today = lambda tz: TOMORROW
        self.store.increment_today("US/Central")
        self.store.increment_today("US/Central")

        self.store._today = original_today  # restore
        self.assertEqual(self.store.get_today_count("US/Central"), 0)

        self.store._today = lambda tz: TOMORROW
        self.assertEqual(self.store.get_today_count("US/Central"), 2)

    # ------------------------------------------------------------------
    # Persistence across close/reopen
    # ------------------------------------------------------------------

    def test_db_survives_close_and_reopen(self):
        """Data persists after closing and reopening the ChallengeStore."""
        self.store.increment_today("US/Central")
        self.store.increment_today("US/Central")
        self.store.increment_today("US/Central")
        self.store.close()

        reopened = self._make_store(self._tmp.name)
        try:
            self.assertEqual(reopened.get_today_count("US/Central"), 3)
        finally:
            reopened.close()

    # ------------------------------------------------------------------
    # Migrations
    # ------------------------------------------------------------------

    def _user_version(self, store: ChallengeStore) -> int:
        return store._conn.execute("PRAGMA user_version").fetchone()[0]

    def _tables(self, store: ChallengeStore) -> set:
        rows = store._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        return {row[0] for row in rows}

    def test_fresh_db_is_fully_migrated(self):
        self.assertEqual(self._user_version(self.store), len(ChallengeStore._MIGRATIONS))
        self.assertTrue({"daily_challenges", "challenge_wins"} <= self._tables(self.store))

    def test_migrates_pre_issue_5_db_and_keeps_counts(self):
        """A DB created before versioning (user_version 0) is upgraded in place."""
        self.store.close()
        os.unlink(self._tmp.name)

        conn = sqlite3.connect(self._tmp.name)
        conn.execute("CREATE TABLE daily_challenges (date TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT INTO daily_challenges (date, count) VALUES (?, 4)", (TODAY,))
        conn.commit()
        conn.close()

        self.store = self._make_store(self._tmp.name)
        self.store._today = lambda tz: TODAY
        self.assertEqual(self._user_version(self.store), 2)
        self.assertIn("challenge_wins", self._tables(self.store))
        self.assertEqual(self.store.get_today_count("US/Central"), 4)

    def test_reopen_is_idempotent(self):
        self.store.record_win("US/Central", 1, 3221, 100)
        self.store.close()

        self.store = self._make_store(self._tmp.name)
        self.assertEqual(self._user_version(self.store), 2)
        self.assertEqual(self.store.get_today_win_count("US/Central"), 1)

    # ------------------------------------------------------------------
    # Wins
    # ------------------------------------------------------------------

    def test_win_count_is_zero_when_no_wins(self):
        self.assertEqual(self.store.get_today_win_count("US/Central"), 0)

    def test_record_win_counts_each_challenge(self):
        self.assertTrue(self.store.record_win("US/Central", 1, 3221, 100))
        self.assertTrue(self.store.record_win("US/Central", 2, 4510, 200))
        self.assertEqual(self.store.get_today_win_count("US/Central"), 2)

    def test_record_win_ignores_duplicate_challenge(self):
        self.assertTrue(self.store.record_win("US/Central", 1, 3221, 100))
        self.assertFalse(self.store.record_win("US/Central", 1, 3221, 100))
        self.assertEqual(self.store.get_today_win_count("US/Central"), 1)

    def test_win_counts_are_per_day(self):
        original_today = self.store._today
        self.store._today = lambda tz: TOMORROW
        self.store.record_win("US/Central", 1, 3221, 100)

        self.store._today = original_today
        self.assertEqual(self.store.get_today_win_count("US/Central"), 0)


if __name__ == "__main__":
    unittest.main()
