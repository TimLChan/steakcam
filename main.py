import os
import subprocess
import helper
import time
import requests
import re
import random
#from rapidocr import RapidOCR

session = requests.session()
# ocrEngine = RapidOCR(
#     params={"Global.lang_det": "en_mobile", "Global.lang_rec": "en_mobile"}
# )

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Origin': 'https://v.angelcam.com',
    'DNT': '1',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
}

tsFileRegex = re.compile('(.*.ts)')
m3u8Regex = re.compile('source[\': ]+(.*)\',')

def getM3u8(url):
    helper.logmessage("getting m3u8")
    videoFeed = requests.get(url, headers=headers)
    if videoFeed.status_code != 200:
        helper.logmessage(f"error fetching playlist, http {videoFeed.status_code} received")
        return False
    m3u8Urls = m3u8Regex.findall(videoFeed.text)
    if len(m3u8Urls) == 0:
        helper.logmessage(f"could not find playlist on page")
        return False
    return m3u8Urls[0]


def downloadVideo(m3u8url):
    helper.logmessage("downloading video")
    m3u8Payload = requests.get(m3u8url, headers=headers)
    if m3u8Payload.status_code != 200:
        helper.logmessage(f"error fetching video, http {m3u8Payload.status_code} received")
        return False
    tsFiles = tsFileRegex.findall(m3u8Payload.text)
    if len(tsFiles) == 0:
        helper.logmessage(f"could not find files in playlist")
        return False
    tsFileUrl = m3u8url.split("playlist.m3u8")[0] + tsFiles[-1]
    videoFile = session.get(tsFileUrl, headers=headers)
    with open("video.ts", "wb") as f:
        f.write(videoFile.content)
    return "video.ts"

def getFrame(file, randomFrame=False):
    helper.logmessage("cleaning frames")
    if not os.path.isfile(file):
        helper.logmessage(f"{file} does not exist")
        return False

    """
    Crop Positions

    First set of clocks are at
    width: 650px - 1400px (750px wide)
    height: 0px - 110px (110px long)
    this is "crop=720:110:650:0"
    note that a box needs to be drawn as well due to the security cam time
    drawbox=x=0:y=80:w=160:h=30:color=black:t=fill

    Second set of clocks are at
    width: 1550px - 2350px (800px wide)
    height: 40px - 170px (130px long)
    this is "crop=800:130:1550:40"


    First Clock
    x: 650
    y: 0
    w: 230
    h: 80
    this is "crop=230:80:650:0"

    Second Clock
    x: 870
    y: 10
    w: 230
    h: 90
    this is "crop=230:90:870:10"

    Third Clock
    x: 870
    y: 10
    w: 230
    h: 90
    this is "crop=230:90:870:10"

    Fourth Clock
    x: 870
    y: 10
    w: 230
    h: 90
    this is "crop=230:90:870:10"

    """
    filenames = []
    #clocks = [("left", "crop=720:110:650:0,drawbox=x=0:y=80:w=160:h=30:color=black:t=fill"), ("right", "crop=800:130:1550:40")]
    clocks = [("clock1", "crop=230:80:650:0")]
    frame = 2
    if random:
        frame = random.randint(1, 6000)
    for clock in clocks:
        filename = f"tests/%04d-{clock[0]}.jpg"
        filenames.append(filename)
        command = [
            "ffmpeg",
            "-i", file,
            #'-vf', f'select=eq(n\,{frame}),{clock[1]}',
            #'-vframes', '1',
            '-vf', f'fps=1/4,{clock[1]}',
            filename
        ]
        commandExec = subprocess.run(command, capture_output=False, stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
        if commandExec.returncode != 0:
            helper.logmessage("something went wrong when cutting frames")
            return False
    return filenames

def ocrFrame(filename):
    helper.logmessage(f"ocring {filename}")
    result = ocrEngine(filename)
    helper.logmessage(result.txts)
    helper.logmessage(result.scores)


angelcamUrl = "https://v.angelcam.com/iframe?v=9klzdgn2y4&autoplay=1"

#lem3u8 = getM3u8(angelcamUrl)
#downloadedVideoFile = downloadVideo(lem3u8)
downloadedVideoFile = "record.ts"
frames = getFrame(downloadedVideoFile, randomFrame=True)

#for frame in frames:
#    ocrFrame(frame)
