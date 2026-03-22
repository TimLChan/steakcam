import re

import requests

import helper
from config import HEADERS


class AngelcamClient:
    """Fetches AngelCam page, parses the m3u8 playlist URL, and downloads video segments."""

    def __init__(self, session: requests.Session):
        self.session = session
        self._m3u8_regex = re.compile(r"source[\': ]+(.*)',")
        self._ts_file_regex = re.compile(r"(.*.ts)")

    def get_m3u8(self, url: str) -> tuple[str, bool]:
        """Fetch the AngelCam page and extract the m3u8 playlist URL.

        Returns:
            (m3u8_url, is_error) — on failure the url may be ``"is_borked"``.
        """
        is_err = False
        m3u8_urls: list[str] = []
        helper.logmessage("=============== getting m3u8 ================")
        try:
            video_feed = self.session.get(url, headers=HEADERS, timeout=10)
            if video_feed.status_code != 200:
                helper.writelogmessage(f"error fetching playlist, http {video_feed.status_code} received")
                m3u8_urls.append("is_borked")
                is_err = True
            m3u8_urls = self._m3u8_regex.findall(video_feed.text)
            if len(m3u8_urls) == 0:
                helper.writelogmessage("could not find playlist on page")
                m3u8_urls.append("is_borked")
                is_err = True
        except Exception as e:
            helper.writelogmessage("error fetching playlist")
            helper.writelogmessage(e)
            m3u8_urls.append("is_borked")
            is_err = True
        return m3u8_urls[0], is_err

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
