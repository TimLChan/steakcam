import atexit
import requests
import signal
import sys
import helper
from clients.angelcam_client import AngelcamClient
from clients.discord_client import DiscordNotifier
from services.frame_pipeline import FramePipeline
from services.stream_manager import StreamManager
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
stream_manager = StreamManager(settings)

first = True  # debug flag: suppresses alerts on first poll cycle

def cleanup_handler(signum, frame):
    """Ensure FFmpeg process is terminated on exit."""
    helper.logmessage(f"Received signal {signum}, shutting down gracefully...")
    stream_manager.stop_stream(reason="signal")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, cleanup_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_handler)  # systemd stop / kill

    # Ensure stream stops on normal exit
    atexit.register(stream_manager.stop_stream, reason="shutdown")

    run_forever(
        first=first,
        settings=settings,
        state=state,
        angelcam=angelcam,
        pipeline=pipeline,
        notifier=notifier,
        stream_manager=stream_manager,
    )
