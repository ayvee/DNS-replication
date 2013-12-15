import os
import sys
import time
import random
import signal
import socket
import httplib
import tempfile
import subprocess
import Queue
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

proxyLockFilePath = ""
downloadTimeoutSec = 20
iterations = 4
browser = webdriver.Firefox()
#browser = webdriver.Chrome('./chromedriver')

allDomains = []

class Trial:
    def __init__(self,websiteID,reps):
        self.numReps = reps
        self.waitTime = 10*random.random()+0.1
        self.websiteID = websiteID

def getURL(website):
    return "http://"+website

def getDefaultResolver():
    resolvFile = open("/etc/resolv.conf",'r')
    rv = ""
    for line in resolvFile:
        line = line.replace('\n','').strip()
        if line[0] == '#' or len(line) < len("nameserver "):
            continue
        if line[:11] == "nameserver ":
            rv = line[11:]
    resolvFile.close()
    if(rv == ""):
        print "Failed to get default resolver"
        exit(1)
    return rv

def getDownloadTimeMicroSecond(url):
    global browser
    global downloadTimeoutSec
    success = False
    downloadTime = 0
    numRetries = 0
    while(success == False):
        print "Downloading "+str(url)
        start = datetime.now()
        try:
            browser.get(url)
            wait = WebDriverWait(browser, downloadTimeoutSec, poll_frequency=0.08)\
                .until(lambda drv: drv.execute_script("return document.readyState") == "complete")
        except Exception as e:
            print e
            browser = webdriver.Firefox()
            if(numRetries == 2):
                return downloadTimeoutSec*1000*1000
            numRetries += 1
            continue
        end = datetime.now()
        diff = end - start
        downloadTime = diff.seconds * 1000 * 1000 + diff.microseconds
        success = True
    return downloadTime

def setResolver(resolver):
    rv = os.system("sudo echo \"nameserver "+str(resolver)+"\" > /etc/resolv.conf")
    if rv != 0:
        print "failed to set resolver to "+str(resolver)
        exit(1)

def getRandomDnsList(defaultDns,lst,numNeeded):
    if(numNeeded > len(lst)):
        numNeeded = len(lst)
    ret = []
    random.shuffle(lst)
    ret.append(defaultDns)
    for i in range(numNeeded-1):
        ret.append(lst[i])
    return ret

def writeResult(trial,time,fileHandle):
    string = str(trial.numReps)+","+str(allDomains[trial.websiteID])+","+str(time)
    fileHandle.write(string+"\n")
    fileHandle.flush()
    os.fsync(fileHandle)

###################################################################################

def main():
    if len(sys.argv) != 5:
        print "incorrect args"
        exit()

    if os.getuid() != 0:
        print "Needs root permission"
        exit()

    proxyBin = sys.argv[1]
    proxyLockFilePath = sys.argv[2]
    dnsListFile = open(sys.argv[3])
    domainListFile = open(sys.argv[4])
    resultFile = open("result.csv","w")
    defaultResolver = getDefaultResolver()
    allTrials = []
    allDnsServers = []
    lastRunTime = {}

    DEVNULL = open(os.devnull,'wb')

    print "Default resolver: "+defaultResolver

    for thisDomain in domainListFile:
        allDomains.append(thisDomain.rstrip())

    for thisServer in dnsListFile:
        allDnsServers.append(thisServer.rstrip())

    dnsListFile.close()
    domainListFile.close()

    for i in range(iterations):
        for id in range(len(allDomains)):
            allTrials.append(Trial(id,1))
            allTrials.append(Trial(id,3))
            lastRunTime[id] = -1

    random.shuffle(allTrials)

    for trial in allTrials:
        currTime = time.time()
        lastRunAt = lastRunTime[trial.websiteID]
        # if last run on the same website was within 60s, sleep
        if(currTime - lastRunAt < 60):
            sleepTime = 60 - (currTime - lastRunAt)+1
            print "Sleeping for "+str(sleepTime)+"s"
            time.sleep(sleepTime)
        lastRunTime[trial.websiteID] = time.time()
        if(trial.numReps > 1):
            tempDNSFile = tempfile.NamedTemporaryFile(delete=False)
            dnsList = getRandomDnsList(defaultResolver,allDnsServers,trial.numReps)
            for i in dnsList:
                tempDNSFile.write(i+"\n")
            tempDNSFile.close()

            proxy = subprocess.Popen([proxyBin,'-f',tempDNSFile.name], stdout=DEVNULL, stderr=DEVNULL)
            setResolver("127.0.0.1")

            # make sure the server is up by checking its active lock file
            lockFile = None
            while True:
                try:
                    lockFile = open(proxyLockFilePath,'r')
                    break
                except IOError:
                    pass
                else:
                    content = lockFile.readline().split(',')
                    startTime = int(content[0])
                    replication = int(content[1])
                    if(replication == trial.numReps):
                        break
                finally:
                    time.sleep(0.1)

            runtime = getDownloadTimeMicroSecond(getURL(allDomains[trial.websiteID]))
            assert(proxy.returncode == None)
            writeResult(trial,runtime,resultFile)
            os.kill(proxy.pid,signal.SIGQUIT)
            proxy.wait()
            os.remove(tempDNSFile.name)
        else:
            setResolver(defaultResolver)
            runtime = getDownloadTimeMicroSecond(getURL(allDomains[trial.websiteID]))
            writeResult(trial,runtime,resultFile)

    resultFile.close()
    setResolver(defaultResolver)
    DEVNULL.close()
    browser.quit()
    
    
if(__name__ == '__main__'):
    main()

