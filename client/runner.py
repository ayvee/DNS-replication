import os
import sys
import time
import random
import signal
import tempfile
import subprocess
import Queue
from datetime import datetime

cmd = "/usr/bin/wget --timeout=8 -e robots=off -U \"Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0\" --page-requisites --no-check-certificate "
iterations = 10

historyQueue = Queue.Queue(70)
allDomains = []

class Trial:
    def __init__(self,websiteID,reps):
        self.numReps = reps
        self.waitTime = 10*random.random()+0.1
        self.websiteID = websiteID

def ifNeedSleep(trial):
    l = list(historyQueue.queue)
    for history in l:
        if(trial.websiteID == l):
            return True
    return False

def getCommand(website):
    return cmd+" "+website+" &>/dev/null"

def getDefaultResolver():
    resolvFile = open("/etc/resolv.conf",'r')
    for line in resolvFile:
        line = line.replace('\n','').strip()
        if line[0] == '#' or len(line) < len("nameserver "):
            continue
        if line[:11] == "nameserver ":
            return line[11:]
    resolvFile.close()

def timedExecuteMicroSecond(cmd):
    assert len(cmd)>0
    start = datetime.now()
    os.system(cmd)
    end = datetime.now()
    diff = end - start
    os.system("for i in $(ls -d */); do sudo rm -rf $i; done")
    return diff.seconds*1000000+diff.microseconds

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

    DEVNULL = open(os.devnull,'wb')

    print "using "+defaultResolver+" as default resolver"

    for thisDomain in domainListFile:
        allDomains.append(thisDomain.rstrip())

    for thisServer in dnsListFile:
        allDnsServers.append(thisServer.rstrip())

    dnsListFile.close()
    domainListFile.close()

    for i in range(iterations):
        for id in range(len(allDomains)):
            allTrials.append(Trial(id,1))
            allTrials.append(Trial(id,1))
            allTrials.append(Trial(id,1))
            allTrials.append(Trial(id,1))
            allTrials.append(Trial(id,1))
            allTrials.append(Trial(id,2))
            allTrials.append(Trial(id,3))
            allTrials.append(Trial(id,4))
            allTrials.append(Trial(id,5))
            allTrials.append(Trial(id,6))

    random.shuffle(allTrials)

    for trial in allTrials:
        if(ifNeedSleep(trial)):
            time.sleep(trial.waitTime)
        try:
            historyQueue.put(trial.websiteID)
        except Queue.Full:
            historyQueue.get()
        if(trial.numReps != 1):
            tempDNSFile = tempfile.NamedTemporaryFile()
            dnsList = getRandomDnsList(defaultResolver,allDnsServers,trial.numReps)
            for i in dnsList:
                tempDNSFile.write(i+"\n")
            tempDNSFile.close()

            proxy = subprocess.Popen([proxyBin,'-f',tempDNSFile.name], stdout=DEVNULL, stderr=DEVNULL)
            setResolver("127.0.0.1")
            time.sleep(1)
            runtime = timedExecuteMicroSecond(getCommand(allDomains[trial.websiteID]))
            assert(proxy.returncode == None)
            writeResult(trial,runtime,resultFile)
            os.kill(proxy.pid,signal.SIGQUIT)
            proxy.wait()
            #os.remove(tempDNSFile.name)
        else:
            setResolver(defaultResolver)
            runtime = timedExecuteMicroSecond(getCommand(allDomains[trial.websiteID]))
            writeResult(trial,runtime,resultFile)

    resultFile.close()
    setResolver(defaultResolver)
    DEVNULL.close()
    
    
if(__name__ == '__main__'):
    main()

