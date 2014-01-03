#!/usr/bin/env python
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
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

import logging
logging.basicConfig(level = logging.INFO, format = "[%(asctime)s] %(levelname)s: %(message)s")
log = logging.getLogger()

# we will load no more than one page every minTrialDuration seconds to avoid
# overloading the local DNS server
minTrialDuration = 30
outputFilenames = "/proj/UIUCScheduling/dns/results/result%d.csv"

proxyLockFilePath = ""
allDomains = []

def getDefaultBrowser():
    #return webdriver.Firefox()
    return webdriver.Chrome('./chromedriver')

def getURL(website):
    return "http://"+website

def getDefaultResolver():
    from shutil import copy as cp
    if not os.path.isfile("/etc/resolv.conf.orig"):
        cp("/etc/resolv.conf", "/etc/resolv.conf.orig")
    resolvFile = open("/etc/resolv.conf",'r')
    rv = ""
    for line in resolvFile:
        line = line.replace('\n','').strip()
        if line[0] == '#' or len(line) < len("nameserver "):
            continue
        if line[:11] == "nameserver ":
            rv = line[11:]
    resolvFile.close()
    if rv == "":
        log.error("Failed to get default resolver")
        exit(1)
    if rv == "127.0.0.1" or rv == "localhost":
        log.error("Default resolver is localhost: something went wrong")
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

def getDownloadTimeWebdriver(url):
    downloadTimeoutSec = 20
    succeeded = False
    downloadTime = 0
    numRetries = 0
    log.info("Downloading "+str(url))
    #start = datetime.now()
    driver = None
    try:
        driver = getDefaultBrowser()
        time.sleep(5) # for browser init
        driver.get(url)
        wait = WebDriverWait(driver, downloadTimeoutSec, poll_frequency=5).\
                until(lambda drv: drv.execute_script("return document.readyState") == "complete")
        if not wait:
            return downloadTimeoutSec
        else:
            exectime = driver.execute_script("return performance.timing.loadEventEnd - performance.timing.navigationStart")
            return float(exectime) * 1e-3
    except Exception as e:
        log.error(e)
        return downloadTimeoutSec
    finally:
        driver.quit()
    #end = datetime.now()
    #diff = end - start
    #downloadTime = diff.seconds * 1000 * 1000 + diff.microseconds

def setResolver(resolver):
    rv = os.system("echo \"nameserver "+str(resolver)+"\" > /etc/resolv.conf")
    if rv != 0:
        log.error("failed to set resolver to "+str(resolver))
        exit(1)

def getDnsList(lst, numNeeded):
    # disabling randomization for now, need to think about whether it's desirable
    #random.shuffle(lst)
    return lst[:numNeeded]

# TODO: may want to make this a context manager instead of the explicit done()
# potential TODO: have collector buffer results in memory and output stats
#                 directly at the end using the classes from util.py
class ResultCollector:
    def __init__(self, maxNumReps = None, outputFilenameFormat = outputFilenames):
        self.outputFilenameFormat = outputFilenameFormat
        #if maxNumReps is not None:
        #    # truncate all output files
        #    for n in xrange(1, maxNumReps+1):
        #        with open(self.outputFilenameFormat % n, 'w'):
        #            pass

    def update(self, numReps, website, time):
        with open(self.outputFilenameFormat % numReps, 'a') as outf:
            outf.write("{website},{time}\n".format(**locals()))

    def done(self):
        pass

class Proxy:
    def __init__(self, proxyBin, proxyLockFile, dnsServers, outputFD):
        self.proxyBin = proxyBin
        self.proxyLockFile = proxyLockFile
        self.dnsServers = dnsServers
        self.outputFD = outputFD
        self.process = None

    def __enter__(self):
        self.dnsFile = dnsFile = tempfile.NamedTemporaryFile(delete=False)
        dnsFile.write("\n".join(self.dnsServers) + '\n')
        dnsFile.close()

        try:
            setResolver("127.0.0.1")
            log.debug("%s -f %s" % (self.proxyBin, dnsFile.name))
            self.process = subprocess.Popen([self.proxyBin,'-f', dnsFile.name], stdout = self.outputFD, stderr = self.outputFD)
        except:
            os.unlink(dnsFile.name)
            raise
        return self

    def waitTillSetUp(self):
        "wait for proxy to come up"
        while True:
            try:
                with open(self.proxyLockFile, 'r') as lockf:
                    content = lockf.readline().split(',')
                    startTime = int(content[0])
                    replication = int(content[1])
                    if replication == len(self.dnsServers):
                        break
            except IOError as e:
                time.sleep(0.1)

    def __exit__(self, typ, value, traceback):
        try:
            process = self.process
            if process.returncode is not None:
                log.error("Proxy process died before we were done with it")
            else:
                os.kill(process.pid,signal.SIGQUIT)
                process.wait()
        finally:
            os.unlink(self.dnsFile.name)

################################################################################

def main():
    if len(sys.argv) != 5:
        print "SYNTAX: %s <proxy_binary> <proxy_lock_file> <dns_servers_list> <domains_list>" % sys.argv[0]
        exit(2)

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

    log.info("Default resolver: "+defaultResolver)
    allDnsServers.append(defaultResolver)

    for thisDomain in domainListFile:
        allDomains.append(thisDomain.rstrip())

    for thisServer in dnsListFile:
        allDnsServers.append(thisServer.rstrip())

    dnsListFile.close()
    domainListFile.close()

    resultCollector = None
    try:
        resultCollector = ResultCollector(len(allDnsServers))
        while True:
            currTime = datetime.now()
            
            numReps = random.randint(1, len(allDnsServers))
            website = random.choice(allDomains)
            def doLookup(numReps, website):
                runtime = getDownloadTimeWebdriver(getURL(website))
                #runtime = getDownloadTimeWget(getURL(allDomains[trial.websiteID]))
                resultCollector.update(numReps, website, runtime)
            if(numReps > 1):
                dnsServers = getDnsList(allDnsServers, numReps)
                log.debug("%d servers: %s; allDnsServers = %s", numReps, dnsServers, allDnsServers)
                with Proxy(proxyBin, proxyLockFilePath, dnsServers, DEVNULL) as proxy:
                    proxy.waitTillSetUp()
                    doLookup(numReps, website)
            else:
                setResolver(defaultResolver)
                doLookup(numReps, website)

            nextTrialAt = currTime + timedelta(seconds = minTrialDuration)
            sleepDuration = (nextTrialAt - datetime.now()).total_seconds()
            if sleepDuration > 0:
                time.sleep(sleepDuration)
    finally:
        setResolver(defaultResolver)
        if resultCollector is not None:
            resultCollector.done()
    DEVNULL.close()

if __name__ == '__main__':
    main()
