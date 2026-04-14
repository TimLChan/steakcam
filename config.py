"""Runtime constants — single source of truth for values used across modules."""

# Business hours (Big Texan restaurant, Amarillo TX)
DEFAULT_OPEN_TIME = "08:00"
DEFAULT_CLOSE_TIME = "23:00"
DEFAULT_TIMEZONE = "US/Central"

# Persistence
CONFIG_FILE = "config.json"
DB_FILE = "challenges.db"

# AngelCam defaults
DEFAULT_VIDEO_URL = "https://v.angelcam.com/iframe?v=9klzdgn2y4&autoplay=1"
DEFAULT_STREAM_URL = "https://www.bigtexan.com/live-stream/"

# HTTP headers for AngelCam requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://v.angelcam.com",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

# Clock crop definitions (ffmpeg format: w:h:x:y)
CLOCK_CROP_DEFINITIONS = [
    ("clock1", "crop=240:100:720:37"),
    ("clock2", "crop=240:100:950:40"),
    ("clock3", "crop=240:100:1190:50"),
    ("clock4", "crop=240:100:1620:70"),
    ("clock5", "crop=240:100:1870:85"),
    ("clock6", "crop=240:100:2100:100"),
]
