import time
from datetime import datetime, timezone

import requests

import helper

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


class DiscordNotifier:
    """Sends Discord webhook notifications for steak challenge alerts."""

    def __init__(self, discord_config: dict, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self._name = discord_config["name"].lower()
        self._avatar_url = discord_config["avatar"]
        self._webhooks = discord_config["webhooks"]

    def send_wrapup(self, daily_challenge_count: int, timezone_name: str, first: bool) -> None:
        """Send an end-of-day wrapup message summarising the number of challenges."""
        if first:
            return
        formatted_date = helper.getFormattedDate(timezone_name)
        payload = {
            "username": self._name,
            "avatar_url": self._avatar_url,
            "embeds": [
                {
                    "title": f"Steak Challenge Wrapup for {formatted_date}",
                    "fields": [
                        {
                            "name": "challengers today",
                            "value": f"{daily_challenge_count} challengers",
                            "inline": "false",
                        }
                    ],
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
        youtube_stream_url: str | None = None,
    ) -> None:
        """Send a steak challenge alert to all configured webhooks.

        Args:
            first: Debug flag — suppresses alerts on the first poll cycle.
            timer: Timer position (1-indexed from left).
            time_remaining: Raw timer value (e.g. 4523 = 45:23).
            stream_url: URL to the Angelcam live stream.
            current_time: Formatted current time string for the embed.
            youtube_stream_url: Optional YouTube stream URL when restreaming is active.
        """
        if first or time_remaining == 5000:
            return

        timer_remaining_str = str(time_remaining)
        if len(timer_remaining_str) == 4:
            timer_remaining_str = f"{timer_remaining_str[:2]}:{timer_remaining_str[2:]}"
        elif len(timer_remaining_str) == 3:
            timer_remaining_str = f"0{timer_remaining_str[:1]}:{timer_remaining_str[1:]}"

        # Build embed fields
        fields = [
            {
                "name": "timer position (from left)",
                "value": f"timer {timer}",
                "inline": "true",
            },
            {
                "name": "time remaining",
                "value": timer_remaining_str,
                "inline": "true",
            },
            {
                "name": "time @ the big texan",
                "value": current_time,
                "inline": "false",
            },
            {
                "name": "angelcam stream",
                "value": f"**[watch stream]({stream_url})**",
                "inline": "false",
            },
        ]

        # Add YouTube stream link if available
        if youtube_stream_url:
            fields.append({
                "name": "youtube stream",
                "value": f"**[watch on youtube]({youtube_stream_url})**",
                "inline": "false",
            })

        payload = {
            "username": self._name,
            "avatar_url": self._avatar_url,
            "embeds": [
                {
                    "title": "New Steak Challenger Identified",
                    "fields": fields,
                    "footer": {"text": f"tracked by timbot-{self._name}-de1"},
                    "timestamp": str(datetime.now(timezone.utc)),
                }
            ],
        }

        for webhook in self._webhooks:
            self._send_with_retry(webhook, payload)
            time.sleep(0.4)

    def _send_with_retry(self, webhook: dict, payload: dict) -> None:
        """Attempt to POST *payload* to a single webhook, retrying up to MAX_RETRIES."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                helper.logmessage(f"sending notification to {webhook['name']} (attempt {attempt})")
                resp = self.session.post(
                    webhook["url"],
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 204:
                    return  # success
                helper.logmessage(f"discord returned {resp.status_code}: {resp.text}")
            except Exception as e:
                helper.logmessage(f"error sending to discord: {e}")

            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_BASE ** attempt
                helper.logmessage(f"retrying in {backoff}s...")
                time.sleep(backoff)

        helper.writelogmessage(f"failed to send to webhook {webhook['name']} after {MAX_RETRIES} attempts")
