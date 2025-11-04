import helper
import json
import time


def saveConfig(data):
    with open("config.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.flush()


def MigrateConfig():
    # this helps migrate old configuration files to newer ones with hopefully no loss of functionality

    with open("config.json", "r") as f:
        ocrConfig = json.load(f)

    # timers - this is the list of timers that are being tracked
    # default - (6000, False, runTime)
    if "timers" not in ocrConfig:
        runTime = int(time.time())
        ocrConfig["timers"] = [(6000, False, runTime), (6000, False, runTime), (6000, False, runTime), (6000, False, runTime), (6000, False, runTime), (6000, False, runTime)]
        saveConfig(ocrConfig)
        helper.logmessage("migration - tracking of timers has been added to the config file.")

    # shouldSendWrapup - this feature will send a discord notification when the store is closed with the daily steak challenge count
    # default - false
    if "shouldSendWrapup" not in ocrConfig or ocrConfig["shouldSendWrapup"] == None:
        ocrConfig["shouldSendWrapup"] = False
        saveConfig(ocrConfig)
        helper.logmessage("migration - shouldSendWrapup defaulted to false. Please update the config to enable the end of day wrapup feature.")

    # videoUrl - this is the url of the video feed
    # default - "https://v.angelcam.com/iframe?v=9klzdgn2y4&autoplay=1"
    if "videoUrl" not in ocrConfig or ocrConfig["videoUrl"] == None:
        ocrConfig["videoUrl"] = "https://v.angelcam.com/iframe?v=9klzdgn2y4&autoplay=1"
        saveConfig(ocrConfig)
        helper.logmessage("migration - videoUrl defaulted to https://v.angelcam.com/iframe?v=9klzdgn2y4&autoplay=1.")
