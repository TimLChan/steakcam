"""Rolling buffer of full frames from recent polls, used to attach a screencap to winner alerts."""

import glob
import os
from collections import deque
from dataclasses import dataclass

import helper


@dataclass(frozen=True)
class Screencap:
    path: str
    readings: list[str]


class ScreencapBuffer:
    """Keeps the full frames (and their timer readings) from the last *max_size* polls.

    Frames are written to *directory* by the caller and the oldest are deleted as new
    ones are added, so at most *max_size* files are kept on disk.
    """

    def __init__(self, directory: str = "screencaps", max_size: int = 3):
        self._directory = directory
        self._max_size = max_size
        self._entries: deque[Screencap] = deque()

        # Frames left over from a previous run have no readings attached, so clear them out
        for stale in glob.glob(os.path.join(directory, "*.jpg")):
            self._remove(stale)

    def path_for(self, poll_time: int) -> str:
        return f"{self._directory}/{poll_time}.jpg"

    def add(self, path: str, readings: list[str]) -> None:
        self._entries.append(Screencap(path=path, readings=list(readings)))
        while len(self._entries) > self._max_size:
            self._remove(self._entries.popleft().path)

    def first_showing(self, timer_index: int, value: int) -> str | None:
        """Return the oldest frame where timer *timer_index* read *value*, i.e. when the clock stopped."""
        for entry in self._entries:
            try:
                if int(entry.readings[timer_index]) == value:
                    return entry.path
            except (ValueError, IndexError):
                continue
        return None

    def _remove(self, path: str) -> None:
        try:
            os.remove(path)
        except Exception as e:
            helper.writelogmessage(f"could not delete {path}, error below:")
            helper.logmessage(e)
