import requests

from clients.angelcam_client import AngelcamClient
from clients.ocr_client import OcrClient
from services.frame_pipeline import FramePipeline
from storage.settings_store import SettingsStore

settings = SettingsStore()
session = requests.Session()
angelcam = AngelcamClient(session)
ocr = OcrClient(settings.ocr_engine_args)
pipeline = FramePipeline(ocr, settings.filter_config)

m3u8, _ = angelcam.get_m3u8(settings.video_url)
video_file, _ = angelcam.download_video(m3u8)

# change full_frame to True to get the full video image
# then refine the co-ordinates in config.py
# set full_frame to False to test the new crop
print(pipeline.get_frames(video_file, full_frame=False, cleanup=False, apply_filters=True))
