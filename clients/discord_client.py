import json
import time
from datetime import datetime, timezone

import requests

import helper

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds
CHALLENGE_SECONDS = 3600
WIN_IMAGE_FILENAME = "winner.jpg"


def _format_timer(value: int) -> str:
    """Format a raw MMSS timer value (e.g. 4523) as ``45:23``."""
    return f"{value // 100:02d}:{value % 100:02d}"


def _format_elapsed(time_remaining: int) -> str:
    """Return how long the challenge took, given the raw MMSS time remaining."""
    remaining_seconds = (time_remaining // 100) * 60 + time_remaining % 100
    elapsed = max(CHALLENGE_SECONDS - remaining_seconds, 0)
    return f"{elapsed // 60:02d}:{elapsed % 60:02d}"


def _pluralise(count: int) -> str:
    return f"{count} challenger" if count == 1 else f"{count} challengers"


def _format_winners(win_count: int, challenger_count: int) -> str:
    """Format the wrapup winners line, e.g. ``1 challenger (10%)``."""
    if challenger_count == 0:
        return _pluralise(win_count)
    return f"{_pluralise(win_count)} ({round(win_count / challenger_count * 100)}%)"


class DiscordNotifier:
    """Sends Discord webhook notifications for steak challenge alerts."""

    def __init__(self, discord_config: dict, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self._name = discord_config["name"].lower()
        self._avatar_url = discord_config["avatar"]
        self._webhooks = discord_config["webhooks"]

    def send_wrapup(
        self,
        daily_challenge_count: int,
        timezone_name: str,
        first: bool,
        win_count: int | None = None,
    ) -> None:
        """Send an end-of-day wrapup message summarising the number of challenges.

        Args:
            win_count: Number of winners today. The winners field is omitted when ``None``.
        """
        if first:
            return
        formatted_date = helper.getFormattedDate(timezone_name)
        fields = [
            {
                "name": "challengers today",
                "value": _pluralise(daily_challenge_count),
                "inline": "false",
            }
        ]
        if win_count is not None:
            fields.append(
                {
                    "name": "winners (beta)",
                    "value": _format_winners(win_count, daily_challenge_count),
                    "inline": "false",
                }
            )
        payload = {
            "username": self._name,
            "avatar_url": self._avatar_url,
            "embeds": [
                {
                    "title": f"Steak Challenge Wrapup for {formatted_date}",
                    "fields": fields,
                    "footer": {"text": f"tracked by timbot-{self._name}-de1"},
                    "timestamp": str(datetime.now(timezone.utc)),
                }
            ],
        }

        for webhook in self._webhooks:
            self._send_with_retry(webhook, payload)
            time.sleep(0.4)

    def send_message(
        self,
        first: bool,
        timer: int = 1,
        time_remaining: int = 6000,
        stream_url: str = "https://www.bigtexan.com/live-stream/",
        current_time: str = "unknown",
    ) -> None:
        """Send a steak challenge alert to all configured webhooks.

        Args:
            first: Debug flag — suppresses alerts on the first poll cycle.
            timer: Timer position (1-indexed from left).
            time_remaining: Raw timer value (e.g. 4523 = 45:23).
            stream_url: URL to the live stream.
            current_time: Formatted current time string for the embed.
        """
        if first or time_remaining == 5000:
            return

        timer_remaining_str = _format_timer(time_remaining)

        payload = {
            "username": self._name,
            "avatar_url": self._avatar_url,
            "embeds": [
                {
                    "title": "New Steak Challenger Identified",
                    "fields": [
                        {
                            "name": "timer position (from left)",
                            "value": f"timer {timer}",
                            "inline": "false",
                        },
                        {
                            "name": "time remaining",
                            "value": timer_remaining_str,
                            "inline": "false",
                        },
                        {
                            "name": "current time @ the big texan",
                            "value": current_time,
                            "inline": "false",
                        },
                        {
                            "name": "link",
                            "value": f"**[watch stream]({stream_url})**",
                            "inline": "false",
                        },
                    ],
                    "footer": {"text": f"tracked by timbot-{self._name}-de1"},
                    "timestamp": str(datetime.now(timezone.utc)),
                }
            ],
        }

        for webhook in self._webhooks:
            self._send_with_retry(webhook, payload)
            time.sleep(0.4)

    def send_win_message(
        self,
        first: bool,
        timer: int,
        time_remaining: int,
        stream_url: str = "https://www.bigtexan.com/live-stream/",
        current_time: str = "unknown",
        image_path: str | None = None,
    ) -> None:
        """Send a (beta) alert that a challenger has likely won.

        Args:
            first: Debug flag — suppresses alerts on the first poll cycle.
            timer: Timer position (1-indexed from left).
            time_remaining: Raw timer value the clock was stopped on (e.g. 3221 = 32:21).
            stream_url: URL to the live stream.
            current_time: Formatted current time string for the embed.
            image_path: Screencap to show in the embed. Sent without an image if it can't be read.
        """
        if first:
            return

        attachment = None
        if image_path is not None:
            try:
                with open(image_path, "rb") as f:
                    attachment = (WIN_IMAGE_FILENAME, f.read())
            except OSError as e:
                helper.writelogmessage(f"could not read screencap {image_path}, sending without it: {e}")

        payload = {
            "username": self._name,
            "avatar_url": self._avatar_url,
            "embeds": [
                {
                    "title": "Steak Challenge Winner (beta)",
                    "fields": [
                        {
                            "name": "timer position (from left)",
                            "value": f"timer {timer}",
                            "inline": "false",
                        },
                        {
                            "name": "time remaining",
                            "value": _format_timer(time_remaining),
                            "inline": "true",
                        },
                        {
                            "name": "finished in",
                            "value": _format_elapsed(time_remaining),
                            "inline": "true",
                        },
                        {
                            "name": "current time @ the big texan",
                            "value": current_time,
                            "inline": "false",
                        },
                        {
                            "name": "link",
                            "value": f"**[watch stream]({stream_url})**",
                            "inline": "false",
                        },
                    ],
                    "footer": {"text": f"tracked by timbot-{self._name}-de1"},
                    "timestamp": str(datetime.now(timezone.utc)),
                }
            ],
        }
        if attachment is not None:
            payload["embeds"][0]["image"] = {"url": f"attachment://{WIN_IMAGE_FILENAME}"}

        for webhook in self._webhooks:
            self._send_with_retry(webhook, payload, attachment)
            time.sleep(0.4)

    def _send_with_retry(self, webhook: dict, payload: dict, attachment: tuple[str, bytes] | None = None) -> None:
        """Attempt to POST *payload* to a single webhook, retrying up to MAX_RETRIES.

        Args:
            attachment: Optional ``(filename, content)`` JPEG, sent as multipart form data.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                helper.logmessage(f"sending notification to {webhook['name']} (attempt {attempt})")
                if attachment is None:
                    resp = self.session.post(
                        webhook["url"],
                        headers={"Content-Type": "application/json"},
                        json=payload,
                    )
                else:
                    filename, content = attachment
                    resp = self.session.post(
                        webhook["url"],
                        data={"payload_json": json.dumps(payload)},
                        files={"files[0]": (filename, content, "image/jpeg")},
                    )
                if resp.status_code in (200, 204):
                    return  # success
                helper.logmessage(f"discord returned {resp.status_code}: {resp.text}")
            except Exception as e:
                helper.logmessage(f"error sending to discord: {e}")

            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_BASE ** attempt
                helper.logmessage(f"retrying in {backoff}s...")
                time.sleep(backoff)

        helper.writelogmessage(f"failed to send to webhook {webhook['name']} after {MAX_RETRIES} attempts")
