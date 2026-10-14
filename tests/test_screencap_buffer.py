"""Tests for the rolling buffer of full frames used by winner alerts."""

import os
import tempfile
import unittest

from services.screencap_buffer import ScreencapBuffer

IDLE = ["6000", "6000", "6000", "6000", "6000", "6000"]


def readings_with(timer_index, value):
    readings = list(IDLE)
    readings[timer_index] = value
    return readings


class TestScreencapBuffer(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def _add(self, buffer, poll_time, readings):
        path = buffer.path_for(poll_time)
        with open(path, "wb") as f:
            f.write(b"jpg")
        buffer.add(path, readings)
        return path

    def test_keeps_only_the_latest_three_frames(self):
        buffer = ScreencapBuffer(self.directory, max_size=3)
        paths = [self._add(buffer, poll_time, IDLE) for poll_time in range(1, 6)]

        self.assertEqual(sorted(os.listdir(self.directory)), ["3.jpg", "4.jpg", "5.jpg"])
        self.assertFalse(os.path.exists(paths[0]))
        self.assertFalse(os.path.exists(paths[1]))

    def test_first_showing_returns_the_frame_where_the_clock_stopped(self):
        buffer = ScreencapBuffer(self.directory)
        self._add(buffer, 1, readings_with(2, "3058"))
        stopped = self._add(buffer, 2, readings_with(2, "3001"))
        self._add(buffer, 3, readings_with(2, "3001"))

        self.assertEqual(buffer.first_showing(2, 3001), stopped)

    def test_first_showing_returns_none_without_a_match(self):
        buffer = ScreencapBuffer(self.directory)
        self._add(buffer, 1, readings_with(2, "3058"))

        self.assertIsNone(buffer.first_showing(2, 3001))
        self.assertIsNone(ScreencapBuffer(self.directory).first_showing(2, 3001))

    def test_unparseable_readings_are_skipped(self):
        buffer = ScreencapBuffer(self.directory)
        self._add(buffer, 1, readings_with(2, "30O1"))
        self._add(buffer, 2, ["3001"])
        stopped = self._add(buffer, 3, readings_with(2, "3001"))

        self.assertEqual(buffer.first_showing(2, 3001), stopped)

    def test_stale_frames_are_cleared_on_startup(self):
        stale = os.path.join(self.directory, "123.jpg")
        other = os.path.join(self.directory, "notes.txt")
        for path in (stale, other):
            with open(path, "wb") as f:
                f.write(b"old")

        ScreencapBuffer(self.directory)

        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(other))


if __name__ == "__main__":
    unittest.main()
