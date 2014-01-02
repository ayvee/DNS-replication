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

iterations = 1
# we will load no more than one page every minTrialDuration seconds to avoid
# overloading the local DNS server
minTrialDuration = 30
outputFilenames = "result%d.csv"

proxyLockFilePath = ""
allDomains = []

def getDefaultBrowser():
    #return webdriver.Firefox()
    return webdriver.Chrome('./chromedriver')

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

def getDownloadTimeWget(url):
    if not os.path.exists("./downloads"):
        os.makedirs("./downloads")
    os.chdir("./downloads")
    cmd = "/usr/bin/wget --timeout=8 -e robots=off -U \"Mozilla/5.0 (X11; Li"+\
          "nux86_64; rv:10.0) Gecko/20100101 Firefox/10.0\" --page-requisit"+\
          "es --no-check-certificate "
    start = datetime.now()
    os.system(cmd+url)
    end = datetime.now()
    diff = end - start
    os.system("rm -rf *")
    os.chdir("..")
    return diff.seconds*1000000+diff.microseconds

def getDownloadTimeWebdriver(driver, url):
    downloadTimeoutSec = 20
    succeeded = False
    downloadTime = 0
    numRetries = 0
    print "Downloading "+str(url)
    #start = datetime.now()
    try:
        driver.get(url)
        wait = WebDriverWait(driver, downloadTimeoutSec, poll_frequency=5)\
            .until(lambda drv: drv.execute_script("return document.readyState") == "complete")
        return float(driver.execute_script("performance.timing.loadEventEnd - performance.timing.navigationStart"))
    except Exception as e:
        print e
        return downloadTimeoutSec*1000*1000
    #end = datetime.now()
    #diff = end - start
    #downloadTime = diff.seconds * 1000 * 1000 + diff.microseconds

def setResolver(resolver):
    rv = os.system("echo \"nameserver "+str(resolver)+"\" > /etc/resolv.conf")
    if rv != 0:
        print "failed to set resolver to "+str(resolver)
        exit(1)

def getRandomDnsList(defaultDns,lst,numNeeded):
    if(numNeeded > len(lst)):
        numNeeded = len(lst)
    random.shuffle(lst)
    return [defaultDns] + lst[:numNeeded-1]

# TODO: may want to make this a context manager instead of the explicit done()
# potential TODO: have collector buffer results in memory and output stats
#                 directly at the end using the classes from util.py
class ResultCollector:
    def __init__(self, maxNumReps = None, outputFilenameFormat = outputFilenames):
        self.outputFilenameFormat = outputFilenameFormat
        if maxNumReps is not None:
            # truncate all output files
            for n in xrange(1, maxNumReps+1):
                with open(self.outputFilenameFormat % n, 'w'):
                    pass

    def update(self, numReps, website, time):
        with open(self.outputFilenameFormat % numReps, 'a') as outf:
            outf.write("{website},{time}\n".format(**locals()))

    def done(self):
        pass

def writeResult(trial,time,fileHandle):
    string = str(trial.numReps)+","+str(allDomains[trial.websiteID])+","+str(time)
    fileHandle.write(string+"\n")
    fileHandle.flush()
    os.fsync(fileHandle)

################################################################################

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
    defaultResolver = getDefaultResolver()
    allTrials = []
    allDnsServers = []

    DEVNULL = open(os.devnull,'wb')

    print "Default resolver: "+defaultResolver

    for thisDomain in domainListFile:
        allDomains.append(thisDomain.rstrip())

    for thisServer in dnsListFile:
        allDnsServers.append(thisServer.rstrip())

    dnsListFile.close()
    domainListFile.close()

    driver = None
    resultCollector = None
    try:
        driver = getDefaultBrowser()
        resultCollector = ResultCollector(allDnsServers.size() + 1)
        while True:
            currTime = time.time()
            numReps = random.randint(1, allDnsServers.size() + 1)
            website = random.choice(allDomains)
    
            if(numReps > 1):
                tempDNSFile = tempfile.NamedTemporaryFile(delete=False)
                dnsList = getRandomDnsList(defaultResolver, allDnsServers, numReps)
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
                        if replication == numReps:
                            break
                    finally:
                        time.sleep(0.1)
    
                runtime = getDownloadTimeWebdriver(getURL(website))
    #            runtime = getDownloadTimeWget(getURL(allDomains[trial.websiteID]))
                assert proxy.returncode is None
                writeResult(numReps, website, runtime)
                os.kill(proxy.pid,signal.SIGQUIT)
                proxy.wait()
                os.remove(tempDNSFile.name)
            else:
                setResolver(defaultResolver)
                runtime = getDownloadTimeWebdriver(getURL(website))
    #            runtime = getDownloadTimeWget(getURL(allDomains[trial.websiteID]))
                resultCollector.update(numReps, website, runtime)
    finally:
        if driver is not None:
            driver.close()
        if resultCollector is not None:
            resultCollector.done()
        setResolver(defaultResolver)
    DEVNULL.close()

if(__name__ == '__main__'):
    main()
