import requests

import helper
from clients.angelcam_client import AngelcamClient
from clients.discord_client import DiscordNotifier
from services.frame_pipeline import FramePipeline
from services.poller import run_forever
from storage.settings_store import SettingsStore
from storage.state_store import StateStore

helper.logmessage("============= loading steakcam ==============")
helper.createfolder("errors")
helper.createfolder("live")
helper.createfolder("train")

helper.logmessage("============== loading config ===============")
settings = SettingsStore()  # loads config.json + runs migrations
state = StateStore()

helper.logmessage("============ loading ocr engine =============")
from clients.ocr_client import OcrClient
ocr = OcrClient(settings.ocr_engine_args)

session = requests.Session()
angelcam = AngelcamClient(session)
notifier = DiscordNotifier(settings.discord_config, session)
pipeline = FramePipeline(ocr, settings.filter_config)

first = True  # debug flag: suppresses alerts on first poll cycle

if __name__ == "__main__":
    run_forever(
        first=first,
        settings=settings,
        state=state,
        angelcam=angelcam,
        pipeline=pipeline,
        notifier=notifier,
    )
