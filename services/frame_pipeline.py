import os
import random
import subprocess
import time

import helper
from clients.ocr_client import OcrClient
from config import CLOCK_CROP_DEFINITIONS
from filters import colour_filter as CustomFilter


class FramePipeline:
    """Orchestrates ffmpeg frame extraction → image filtering → OCR."""

    def __init__(self, ocr_client: OcrClient, filter_config: dict):
        self.ocr_client = ocr_client
        self.filter_config = filter_config  # e.g. {"clock1": True, ...}

    def get_frames(
        self,
        file: str,
        *,
        random_frame: bool = False,
        full_frame: bool = False,
        cleanup: bool = True,
        apply_filters: bool = True,
    ) -> list[str] | bool:
        """Extract clock frames from a video file, apply filters, and OCR each one.

        Returns:
            A list of timer reading strings (e.g. ``["4523", "6000", ...]``),
            or ``False`` if the input file doesn't exist.
        """
        helper.logmessage("============ parse frames and ocr ===========")
        if not os.path.isfile(file):
            helper.logmessage(f"{file} does not exist")
            return False

        timer_times: list[str] = []
        frame = 2
        video_time = int(time.time())

        if random_frame:
            frame = random.randint(1, 60)

        for clock_name, crop_filter in CLOCK_CROP_DEFINITIONS:
            filename = f"live/{video_time}-{clock_name}.jpg"
            command = ["ffmpeg", "-i", file, "-vframes", "1", filename]
            if not full_frame:
                command.insert(3, "-vf")
                command.insert(4, f"select=eq(n\\, {frame}), {crop_filter}")

            command_exec = subprocess.run(
                command,
                capture_output=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

            if command_exec.returncode != 0:
                helper.writelogmessage("something went wrong when cutting frames")
                helper.writelogmessage(command_exec.stderr)
            else:
                if apply_filters and self.filter_config.get(clock_name, False):
                    try:
                        CustomFilter.apply_filter(filename, filename)
                        CustomFilter.replace_with_white(filename, filename)
                    except Exception as e:
                        helper.writelogmessage(f"Error applying filter to {clock_name}: {e}")

                timer_result, timer_confidence = self.ocr_client.check_clock(filename)
                if timer_result != "":
                    timer_times.append(timer_result)
                helper.logmessage(f"{clock_name} result: {timer_result} | confidence: {timer_confidence}")

            if cleanup:
                try:
                    os.remove(filename)
                except Exception as e:
                    helper.writelogmessage(f"could not delete {filename}, error below:")
                    helper.logmessage(e)

        return timer_times
