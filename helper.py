from datetime import datetime
import pytz
import time
import os


def loginput(msg=""):
    return input(('[{}] {}').format(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p'), msg))

def logmessage(msg=""):
    print(('[{}] {}').format(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p'), msg))

def createfolder(foldername):
    if not os.path.exists(foldername):
        os.mkdir(foldername)
        logmessage("Creating Directory: '" + foldername + "'")

def getDateTime():
    return str(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%b %d - %I:%M:%S %p %Z'))

def getlogtime():
    return datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p')

def getTime(timezone="Australia/Melbourne"):
    return datetime.now(pytz.timezone(timezone)).strftime("%H:%M:%S")

def getCurrTimeInInt():
    return int(time.time())

def withinTimePeriod(start="15:58:59", end="16:01:30", timezone="Australia/Melbourne"):
    colons = start.count(":")
    if colons == 2:
        currenttime = datetime.now(pytz.timezone(timezone)).time()
        start = datetime.strptime(start, "%H:%M:%S").time()
        end = datetime.strptime(end, "%H:%M:%S").time()
    else:
        currenttime = datetime.now(pytz.timezone(timezone)).time()
        start = datetime.strptime(start, "%H:%M").time()
        end = datetime.strptime(end, "%H:%M").time()

    #print(f"start: {start}, current: {currenttime}, end: {end}")

    # see whether start or end is a bigger number

    # case 1: start: 08:00, end: 12:00, current: 10:00
    # if the start hour is equal to or smaller than the end hour
    # the time period is within the same day
    if start <= end:
        return start <= currenttime <= end

    # case 2: start: 23:00, end: 12:00, current: 10:00
    # if the start hour is greater than the end hour
    # the time period is on the next day
    else:
        return start <= currenttime or currenttime <= end

def writelogmessage(msg="", file="error.log"):
    message = ('[{}] {}').format(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p'), msg)
    with open(file, 'a') as f:
        f.write(f"{message}\n")
