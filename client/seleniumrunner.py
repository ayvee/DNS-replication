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

iterations = 1

firefox = webdriver.Firefox()

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
    global firefox
    success = False
    downloadTime = 0
    while(success == False):
        print "Downloading "+str(url)
        start = datetime.now()
        try:
            firefox.get(url)
        except httplib.BadStatusLine:
            firefox = webdriver.Firefox()
            continue
        success = True
        end = datetime.now()
        diff = end - start
        downloadTime = diff.seconds*1000000+diff.microseconds
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
    if len(sys.argv) != 4:
        print "incorrect args"
        exit()

    if os.getuid() != 0:
        print "Needs root permission"
        exit()

    proxyBin = sys.argv[1]
    dnsListFile = open(sys.argv[2])
    domainListFile = open(sys.argv[3])
    resultFile = open("result.csv","w")
    defaultResolver = getDefaultResolver()
    allTrials = []
    allDnsServers = []
    allDomains = []
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
        currTime = datetime.now()
        currTime = currTime.seconds * 1000000 + currTime.microseconds
        lastRunAt = lastRunTime[allDomains[trial.websiteID]]
        # if last run on the same website was within 60s, sleep
        if(currTime - lastRunAt < 60*1000*1000):
            sleepTime = 60 - (currTime - lastRunAt)/(1000*1000)+1
            print "Sleeping for "+str(sleepTime)+"s"
            time.sleep(sleepTime)
       
        if(trial.numReps > 1):
            tempDNSFile = tempfile.NamedTemporaryFile(delete=False)
            dnsList = getRandomDnsList(defaultResolver,allDnsServers,trial.numReps)
            for i in dnsList:
                tempDNSFile.write(i+"\n")
            tempDNSFile.close()

            proxy = subprocess.Popen([proxyBin,'-f',tempDNSFile.name], stdout=DEVNULL, stderr=DEVNULL)
            setResolver("127.0.0.1")

            # test to see if the server is up
            test_skt = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            rv = -1
            while(rv != 0):
                rv = test_skt.connect_ex(('127.0.0.1',53))
            test_skt.close()

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
    firefox.quit()
    
    
if(__name__ == '__main__'):
    main()

