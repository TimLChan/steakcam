import json
import requests
import time
import helper
from datetime import datetime

class DiscordYeet(object):

    def __init__(self):
        self.session = requests.session()
        self.config = self.loadConfig()

    def loadConfig(self):
        with open("config.json", "r") as f:
            return json.loads(f.read())

    def SendMessage(self, first, timer=1, timeRemaining=6000, streamUrl="https://www.bigtexan.com/live-stream/"):
        if first:
            return
        timerRemainingStr = str(timeRemaining)
        if len(timerRemainingStr) == 4:
            timerRemainingStr = f"{timerRemainingStr[:2]}:{timerRemainingStr[2:]}"
        elif len(timerRemainingStr) == 3:
            timerRemainingStr = f"0{timerRemainingStr[:1]}:{timerRemainingStr[1:]}"
        try:
            payload = {
                "username": self.config["discord"]["name"].lower(),
                "avatar_url": self.config["discord"]["avatar"],
                "embeds": [{
                    "title": f"New Steak Challenger Identified",
                    "fields": [
                        {
                            "name": "timer position (from left)",
                            "value": f"timer {timer}",
                            "inline": "true"
                        },
                        {
                            "name": "time remaining",
                            "value": timerRemainingStr,
                            "inline": "true"
                        },
                        {
                            "name": "link",
                            "value": f"**[watch stream]({streamUrl})**",
                            "inline": "false"
                        }
                    ],
                    "footer": {'text': f'tracked by timbot-{self.config["discord"]["name"].lower()}-us1'},
                    "timestamp": str(datetime.utcnow())
                }]
            }
            didyeet = False
            while not didyeet:
                for webhook in self.config["discord"]["webhooks"]:
                    helper.logmessage(f"sending notification to {webhook['name']}")
                    discordsend = self.session.post(webhook['url'], headers={"Content-Type": "application/json"}, json=payload)
                    if discordsend.status_code != 204:
                        helper.logmessage("error when sending to discord, trying again!")
                        helper.logmessage(discordsend.text)
                        time.sleep(2)
                        didyeet = False
                    else:
                        didyeet = True
            time.sleep(0.4)
        except Exception as e:
            helper.logmessage("error in SendMessage, error below:")
            helper.logmessage(e)
