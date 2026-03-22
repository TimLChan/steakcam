import shutil
from typing import Any

from paddleocr import TextRecognition

import helper


class OcrClient:
    """Wraps PaddleOCR TextRecognition — keeps engine init out of import side-effects."""

    def __init__(self, engine_args: dict):
        self.engine = TextRecognition(**engine_args)

    @staticmethod
    def numbers_only(text: str) -> str:
        """Strip all non-digit characters from *text*."""
        return "".join(ch for ch in text if ch.isdigit())

    def check_clock(self, filename: str) -> tuple[str, Any]:
        """Run OCR on a cropped clock image and return ``(reading, confidence)``.

        *reading* is a 4-digit string (e.g. ``"4523"``) or ``""`` on failure.
        Side-effects: copies low-confidence frames to ``train/`` and bad reads to ``errors/``.
        """
        clock = ""
        confidence = ""
        try:
            result = self.engine.predict(filename)
            for res in result:
                temp_clock = res["rec_text"]
                temp_clock = self.numbers_only(temp_clock)
                if "rec_score" in res:
                    confidence = res["rec_score"]
                    try:
                        if confidence < 0.8 and confidence > 0.4:
                            training_filename = f"train/{filename.split('/')[-1]}"
                            shutil.copy(filename, training_filename)
                            with open(training_filename.replace("jpg", "txt"), "w") as f:
                                f.write(f"{training_filename},{res['rec_text']},{confidence}\n")
                    except Exception:
                        helper.writelogmessage(f"couldn't save file {filename} to training folder")
                if len(temp_clock) != 4 or int(temp_clock) > 6000:
                    helper.logmessage(f"issue during ocr - ocr: {res['rec_text']}, cleaned: {temp_clock}")
                    if confidence > 0.0:
                        error_filename = f"errors/{filename.split('/')[-1]}"
                        shutil.copy(filename, error_filename)
                        with open(error_filename.replace("jpg", "txt"), "w") as f:
                            f.write(f"ocr: {res['rec_text']}, cleaned: {temp_clock}, confidence: {confidence}\n")
                else:
                    clock = temp_clock
        except Exception as e:
            helper.logmessage("something went wrong when checking timer")
            helper.logmessage(str(e))
        return clock, confidence
