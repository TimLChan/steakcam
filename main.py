import os
import subprocess
import helper
import time
import json
import requests
import re
import random
import shutil
import discord
from paddleocr import TextRecognition

helper.createfolder('errors')
helper.createfolder('live')
helper.createfolder('train')

helper.logmessage("============ loading ocr engine =============")

with open("config.json", "r") as f:
    ocrConfig = json.load(f)

ocr = TextRecognition(**ocrConfig["ocrEngine"]["args"])

session = requests.session()
disc = discord.DiscordYeet()
first = True

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

runTime = int(time.time())

# Using a tuple cause lazy - (currentTimer, hasAlerted, lastResetTime)
# currentTimer is the current number on the board
# hasAlerted is whether there was an alert recently (redundant?)
# lastResetTime is when the clock was last reset to 6000 (60:00) or hit 0000 (00:00)
trackedTimers = [(6000, False, runTime), (6000, False, runTime), (6000, False, runTime), (6000, False, runTime), (6000, False, runTime), (6000, False, runTime)]


tsFileRegex = re.compile('(.*.ts)')
m3u8Regex = re.compile('source[\': ]+(.*)\',')


angelcamUrl = "https://v.angelcam.com/iframe?v=9klzdgn2y4&autoplay=1"
timezone = "US/Central"

# set up end

# functions start

def numbersOnly(text):
    strippedNumber = ""
    for i in range(len(text)):
        if text[i].isdigit():
            strippedNumber = strippedNumber + text[i]
    return strippedNumber


def getM3u8(url):
    isErr = False
    m3u8Urls = []
    helper.logmessage("=============== getting m3u8 ================")
    try:
        videoFeed = requests.get(url, headers=headers)
        if videoFeed.status_code != 200:
            helper.writelogmessage(f"error fetching playlist, http {videoFeed.status_code} received")
            m3u8Urls.append("is_borked")
            isErr = True
        m3u8Urls = m3u8Regex.findall(videoFeed.text)
        if len(m3u8Urls) == 0:
            helper.writelogmessage(f"could not find playlist on page")
            m3u8Urls.append("is_borked")
            isErr = True
    except Exception as e:
        helper.writelogmessage(f"error fetching playlist")
        helper.writelogmessage(e)
        m3u8Urls.append("is_borked")
        isErr = True
    return m3u8Urls[0], isErr


def downloadVideo(m3u8url):
    isErr = False
    helper.logmessage("============= downloading video =============")
    try:
        m3u8Payload = requests.get(m3u8url, headers=headers)
        if m3u8Payload.status_code != 200:
            helper.logmessage(f"error fetching video, http {m3u8Payload.status_code} received")
            isErr = True
        tsFiles = tsFileRegex.findall(m3u8Payload.text)

        if len(tsFiles) == 0:
            helper.writelogmessage(f"could not find files in playlist")
            isErr = True

        tsFileUrl = m3u8url.split("playlist.m3u8")[0] + tsFiles[-1]
        videoFile = session.get(tsFileUrl, headers=headers)

        with open("video.ts", "wb") as f:
            f.write(videoFile.content)
    except Exception as e:
        helper.writelogmessage(f"error downloading video")
        helper.writelogmessage(e)
        isErr = True
    return "video.ts", isErr

def checkClock(filename):
    #helper.logmessage(f"ocring {filename}")
    clock = ""
    confidence = ""
    try:
        result = ocr.predict(filename)

        for res in result:
            tempClock = res['rec_text']
            tempClock = numbersOnly(tempClock)
            if "rec_score" in res:
                confidence = res['rec_score']
                try:
                    if confidence < 0.8 and confidence > 0.0:
                        trainingFileName = f"train/{filename.split('/')[-1]}"
                        shutil.copy(filename, trainingFileName)
                        with open(trainingFileName.replace("jpg", "txt"), "w") as f:
                            f.write(f"{trainingFileName},{res['rec_text']},{confidence}\n")
                except:
                    helper.writelogmessage(f"couldn't save file {filename} to training folder")
            if len(tempClock) != 4:
                helper.logmessage(f"issue during ocr - ocr: {res['rec_text']}, cleaned: {tempClock}")
                errorFileName = f"errors/{filename.split('/')[-1]}"
                shutil.copy(filename, errorFileName)
                with open(errorFileName.replace("jpg", "txt"), "w") as f:
                    f.write(f"ocr: {res['rec_text']}, cleaned: {tempClock}, confidence: {confidence}\n")
            else:
                clock = tempClock
    except Exception as e:
        helper.logmessage("something went wrong when checking timer")
        helper.logmessage(str(e))

    return clock, confidence

def getFrames(file, randomFrame=False):
    helper.logmessage("============ parse frames and ocr ===========")
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
    w: 240
    h: 90
    this is "crop=240:90:650:0"

    Second Clock
    x: 890
    y: 10
    w: 240
    h: 90
    this is "crop=240:90:890:10"

    Third Clock
    x: 1130
    y: 15
    w: 240
    h: 90
    this is "crop=240:90:1150:15"

    Fourth Clock
    x: 1580
    y: 35
    w: 240
    h: 100
    this is "crop=240:100:1580:35"

    Fifth Clock
    x: 1830
    y: 40
    w: 240
    h: 100
    this is "crop=240:100:1830:40"

    Sixth Clock
    x: 2070
    y: 65
    w: 240
    h: 100
    this is "crop=240:100:2070:65"

    """
    clocks = [("clock1", "crop=240:90:650:0"), ("clock2", "crop=240:90:890:10"), ("clock3", "crop=240:90:1130:20"), ("clock4", "crop=240:100:1580:35"), ("clock5", "crop=240:100:1830:40"), ("clock6", "crop=240:100:2070:65")]
    timerTimes = []
    frame = 2

    if randomFrame:
        frame = random.randint(1, 60)
    for clock in clocks:
        filename = f"live/{runTime}-{clock[0]}.jpg"
        command = [
            "ffmpeg",
            "-i", file,
            '-vf', f'select=eq(n\,{frame}),{clock[1]}',
            '-vframes', '1',
            #'-vf', f'fps=1/4,{clock[1]}',
            filename
        ]
        commandExec = subprocess.run(command, capture_output=False, stdout = subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if commandExec.returncode != 0:
            helper.writelogmessage("something went wrong when cutting frames")
            helper.writelogmessage(commandExec.stderr)
        else:
            timerResult, timerConfidence = checkClock(filename)
            if timerResult != "":
                timerTimes.append(timerResult)
            helper.logmessage(f"{clock[0]} result: {timerResult} | confidence: {timerConfidence}")

        try:
            os.remove(filename)
        except Exception as e:
            helper.writelogmessage(f"could not delete {filename}, error below:")
            helper.logmessage(e)

    return timerTimes

# functions end

while True:
    isWithin = helper.withinTimePeriod("08:00", "22:30", timezone)
    sleeptime = 60

    # sleep for 5-10 mins if the restaurant is closed
    if not isWithin:
        helper.logmessage(f"restaurant is closed, current time is {helper.getTime(timezone)}")
        sleeptime = random.randint(300, 600)

    # restaurant open, let's go
    else:
        lem3u8, hasErr = getM3u8(angelcamUrl)
        if hasErr == False:
            downloadedVideoFile, hasErr = downloadVideo(lem3u8)
            if hasErr == False:
                liveTimers = getFrames(downloadedVideoFile, randomFrame=False)

                helper.logmessage("============== checking timers ==============")
                if len(liveTimers) == 6:
                    for counter in range(len(liveTimers)):
                    # compare the timers and their many different states
                        try:
                            currentTime = int(liveTimers[counter])
                            trackedTime = trackedTimers[counter][0]
                            lastResetTime = trackedTimers[counter][2]

                            # case 1: trackedTime = 6000 and currentTime < trackedTime and currenTime != 0
                            # alert if hasAlerted is False, otherwise just ignore
                            if currentTime < trackedTime and trackedTime == 6000 and currentTime != 0:
                                helper.logmessage(f"timer {counter} triggered, steak challenge is on")
                                if not trackedTimers[counter][1]:
                                    disc.SendMessage(first, counter + 1, currentTime, angelcamUrl)
                                trackedTimers[counter] = (currentTime, True, lastResetTime)

                            # case 2: trackedTime < 6000 and currentTime < trackedTime
                            # update the timer but don't send any alerts
                            elif currentTime < trackedTime:
                                trackedTimers[counter] = (currentTime, trackedTimers[counter][1], lastResetTime)

                            # case 3: currentTime hits zero or 6000
                            # set the timer to 6000, reset the alert flag, and also update lastResetTime
                            elif currentTime == 0 or currentTime == 6000:
                                trackedTimers[counter] = (6000, False, helper.getCurrTimeInInt())

                            # case 4: currentTime > trackedTime but the clock was never reset
                            # this is an odd scenario where the same timer is reused due to many
                            # challengers. Because this script polls every 60 - 90s, it may miss
                            # the overlap between resetting and starting the timer again
                            # should only alert again IF the last reset was over 20 minutes ago
                            elif currentTime > trackedTime:
                                if int(time.time()) > (lastResetTime + 1200):
                                    trackedTimers[counter] = (currentTime, True, helper.getCurrTimeInInt())
                                    disc.SendMessage(first, counter + 1, currentTime, angelcamUrl)
                                else:
                                    trackedTimers[counter] = (currentTime, False, lastResetTime)

                            # case 5: currentTime = trackedTime
                            # the clock is... frozen?
                            elif currentTime == trackedTime:
                                continue

                            # case 6: how does this every happen? log something and just capture it
                            else:
                                helper.writelogmessage("how did we get here?")
                                helper.writelogmessage(f"current time for timer {counter}: {currentTime}")
                                helper.writelogmessage(f"tracked payload timer {counter}: {trackedTimers[counter]}")


                        except ValueError as e:
                            helper.writelogmessage(f"couldn't parse timer {counter}, ignoring for now")

                else:
                    helper.writelogmessage(f"expecting 6 times, got {len(liveTimers)}")
        sleeptime = random.randint(60, 90)
    first = False
    helper.logmessage(f"========== sleeping for {sleeptime} seconds ==========")
    time.sleep(sleeptime)
