import requests
import signal
import sys
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

# Global reference to stream_manager for signal handler
_stream_manager = None

def cleanup_handler(signum, frame):
    """Ensure FFmpeg process is terminated on exit."""
    helper.logmessage(f"Received signal {signum}, shutting down gracefully...")
    if _stream_manager is not None:
        _stream_manager.graceful_shutdown()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, cleanup_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_handler)  # systemd stop / kill

    def set_stream_manager_ref(sm):
        global _stream_manager
        _stream_manager = sm

    run_forever(
        first=first,
        settings=settings,
        state=state,
        angelcam=angelcam,
        pipeline=pipeline,
        notifier=notifier,
        stream_manager_ref_setter=set_stream_manager_ref,
    )
