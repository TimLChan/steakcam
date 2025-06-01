from datetime import datetime
import pytz
import time

def logmessage(msg=""):
    print(('[{}] {}').format(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p'), msg))

def writelogmessage(msg="", file="debug.log"):
    message = ('[{}] {}').format(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p'), msg)
    with open(file, 'a') as f:
        f.write(f"{message}\n")

def loginput(msg=""):
    return input(('[{}] {}').format(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p'), msg))
    
def getlogtime():
    return datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%Y-%m-%d %I:%M:%S %p')

def getTime():
    return str(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%I:%M:%S %p %Z - %b %d'))

def getDateTime():
    return str(datetime.now(pytz.timezone('Australia/Melbourne')).strftime('%b %d - %I:%M:%S %p %Z'))

def getCurrTimeInInt():
    return int(time.time())