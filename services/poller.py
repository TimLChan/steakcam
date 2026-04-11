import random
import time

import helper
from clients.angelcam_client import AngelcamClient
from clients.discord_client import DiscordNotifier
from config import DEFAULT_CLOSE_TIME, DEFAULT_OPEN_TIME
from models import TimerState
from services.frame_pipeline import FramePipeline
from services.timer_engine import CASE_IDLE_TRIGGER, CASE_UNCHANGED, evaluate_timer_transition
from storage.settings_store import SettingsStore
from storage.state_store import StateStore


def run_once(
    *,
    first: bool,
    daily_challenge_count: int,
    settings: SettingsStore,
    state: StateStore,
    angelcam: AngelcamClient,
    pipeline: FramePipeline,
    notifier: DiscordNotifier,
) -> tuple[int, int]:
    timezone = settings.timezone
    is_within = helper.withinTimePeriod(DEFAULT_OPEN_TIME, DEFAULT_CLOSE_TIME, timezone)
    sleep_time = 60

    if not is_within:
        if settings.should_send_wrapup and not state.wrapup_sent_today:
            state.wrapup_sent_today = True
            if not first:
                notifier.send_wrapup(daily_challenge_count, settings.timezone, first)
                helper.logmessage(f"sent wrapup: {daily_challenge_count} challengers today")

        daily_challenge_count = 0
        helper.logmessage(f"restaurant is closed, current time is {helper.getTime(timezone)}")
        sleep_time = random.randint(300, 600)
        return daily_challenge_count, sleep_time

    if state.wrapup_sent_today:
        state.wrapup_sent_today = False

    m3u8_url, has_err = angelcam.get_m3u8(settings.video_url)
    if has_err is False:
        downloaded_video_file, has_err = angelcam.download_video(m3u8_url)
        if has_err is False:
            live_timers = pipeline.get_frames(downloaded_video_file, random_frame=False, cleanup=True)

            helper.logmessage("============== checking timers ==============")
            if len(live_timers) == 6:
                tracked_timers = state.tracked_timers
                for counter in range(len(live_timers)):
                    try:
                        current_time = int(live_timers[counter])
                        tracked_state = TimerState.from_legacy(tracked_timers[counter])
                        transition = evaluate_timer_transition(
                            timer_index=counter,
                            current_time=current_time,
                            tracked_timer=tracked_state,
                            now=int(time.time()),
                        )

                        if transition.case == CASE_IDLE_TRIGGER:
                            helper.logmessage(f"timer {counter} triggered, steak challenge is on")

                        if transition.ignored_low_value:
                            helper.logmessage(f"ignoring timer {counter} because {current_time} feels too low")
                            continue

                        if transition.alert_event is not None:
                            # Sanity guard - likely OCR misread
                            if transition.alert_event.time_remaining < 3500:
                                continue
                            # Additional sanity guard added for timer 2 due to CCTV text overlays
                            if transition.alert_event.time_remaining < 5700 and transition.alert_event.timer_position == 2:
                                helper.logmessage(f"timer 2 triggered with abnormal time {transition.alert_event.time_remaining}")
                                continue

                            daily_challenge_count += 1
                            notifier.send_message(
                                first,
                                transition.alert_event.timer_position,
                                transition.alert_event.time_remaining,
                                settings.video_url,
                                helper.getDateTime(timezone),
                            )

                        if transition.case == CASE_UNCHANGED:
                            continue

                        tracked_timers[counter] = transition.timer_state.to_legacy()

                    except ValueError:
                        helper.writelogmessage(f"couldn't parse timer {counter}, ignoring for now")

                state.save()

            else:
                helper.writelogmessage(f"expecting 6 times, got {len(live_timers)}")

    sleep_time = random.randint(60, 90)
    return daily_challenge_count, sleep_time


def run_forever(
    *,
    first: bool,
    settings: SettingsStore,
    state: StateStore,
    angelcam: AngelcamClient,
    pipeline: FramePipeline,
    notifier: DiscordNotifier,
) -> None:
    daily_challenge_count = state.daily_challenge_count
    while True:
        daily_challenge_count, sleep_time = run_once(
            first=first,
            daily_challenge_count=daily_challenge_count,
            settings=settings,
            state=state,
            angelcam=angelcam,
            pipeline=pipeline,
            notifier=notifier,
        )
        first = False
        state.daily_challenge_count = daily_challenge_count
        helper.logmessage(f"========== sleeping for {sleep_time} seconds ==========")
        time.sleep(sleep_time)
