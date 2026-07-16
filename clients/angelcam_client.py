import re

import requests

import helper
from config import HEADERS


class AngelcamClient:
    """Fetches AngelCam page, parses the m3u8 playlist URL, and downloads video segments."""

    def __init__(self, session: requests.Session):
        self.session = session
        self._m3u8_patterns = [
            re.compile(r"'hls'\s*:\s*'([^']*)'"),                            # current page format
            re.compile(r"source[\': ]+([^']*)',"),                            # legacy fallback
            re.compile(r"""['"]([^'"]*\.m3u8[^'"]*)['"]""", re.IGNORECASE),   # general catch-all
        ]
        self._ts_file_regex = re.compile(r"(.*.ts)")
        self._unicode_escape_regex = re.compile(r"\\u([0-9a-fA-F]{4})")

    def _decode_unicode_escapes(self, text: str) -> str:
        """Decode JS-style \\uXXXX escape sequences (e.g. ``\\u002D`` -> ``-``).

        AngelCam embeds the stream URL in JavaScript, so characters such as
        ``-`` (\\u002D) and ``=`` (\\u003D) appear as unicode escapes in the
        page source. Leaving them untouched yields an invalid URL.

        Note - this is fragile and should be uplifted to a more robust solution
        in the future.
        """
        return self._unicode_escape_regex.sub(
            lambda m: chr(int(m.group(1), 16)),
            text,
        )

    def _extract_m3u8(self, html: str) -> str | None:
        """Return the first m3u8 URL found in *html*, or ``None``.

        Patterns are tried in order: the precise ``'hls'`` form and the
        legacy ``source`` form first, then a general catch-all that matches
        any single- or double-quoted string containing ``.m3u8``. Unicode
        escape sequences in the result are decoded.
        """
        for pattern in self._m3u8_patterns:
            match = pattern.search(html)
            if match:
                return self._decode_unicode_escapes(match.group(1))
        return None

    def get_m3u8(self, url: str) -> tuple[str, bool]:
        """Fetch the AngelCam page and extract the m3u8 playlist URL.

        Returns:
            (m3u8_url, is_error) — on failure the url may be ``"is_borked"``.
        """
        helper.logmessage("=============== getting m3u8 ================")
        try:
            video_feed = self.session.get(url, headers=HEADERS, timeout=10)
            if video_feed.status_code != 200:
                helper.writelogmessage(f"error fetching playlist, http {video_feed.status_code} received")
                return "is_borked", True

            m3u8_url = self._extract_m3u8(video_feed.text)
            if m3u8_url is None:
                helper.writelogmessage("could not find playlist on page")
                return "is_borked", True
            return m3u8_url, False
        except Exception as e:
            helper.writelogmessage("error fetching playlist")
            helper.writelogmessage(e)
            return "is_borked", True

    def download_video(self, m3u8_url: str) -> tuple[str, bool]:
        """Download the latest .ts segment from the m3u8 playlist.

        Returns:
            (filename, is_error)
        """
        is_err = False
        helper.logmessage("============= downloading video =============")
        try:
            m3u8_payload = self.session.get(m3u8_url, headers=HEADERS, timeout=10)
            if m3u8_payload.status_code != 200:
                helper.logmessage(f"error fetching video, http {m3u8_payload.status_code} received")
                is_err = True
            ts_files = self._ts_file_regex.findall(m3u8_payload.text)

            if len(ts_files) == 0:
                helper.writelogmessage("could not find files in playlist")
                is_err = True

            ts_file_url = m3u8_url.split("playlist.m3u8")[0] + ts_files[-1]
            video_file = self.session.get(ts_file_url, headers=HEADERS, timeout=10)

            with open("video.ts", "wb") as f:
                f.write(video_file.content)
        except Exception as e:
            helper.writelogmessage("error downloading video")
            helper.writelogmessage(e)
            is_err = True
        return "video.ts", is_err
