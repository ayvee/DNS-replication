import os
import sys
import time
import random
import subprocess
from datetime import datetime

cmd = "/usr/bin/wget --timeout=8 -e robots=off -U \"Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0\" --page-requisites --no-check-certificate "
replicationCap = 7
iterations = 100

class Trail:
    def __init__(self,website):
        self.command = cmd+" "+website+" &>/dev/null"
        randBool = bool(random.getrandbits(1))
        self.ifReplicate = randBool
        if(randBool):
            self.numReps = random.randint(1,replicationCap)
        else:
            self.numReps = 0
        self.waitTime = 10.0 * random.random()+0.01
        self.website = website

def getDefaultResolver():
    resolvFile = open("/etc/resolv.conf",'r')
    for line in resolvFile:
        line = line.replace('\n','').strip()
        if line[0] == '#' or len(line) < len("nameserver "):
            continue
        if line[:11] == "nameserver ":
            return line[11:]

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

def getRandomDnsList(lst,numNeeded):
    if(numNeeded > len(lst)):
        numNeeded = len(lst)
    ret = []
    random.shuffle(lst)
    for i in range(numNeeded):
        ret.append(lst[i])
    return ret

def writeResult(trail,time,fileHandle):
    string = str(trail.numReps)+","+str(trail.website)+","+time
    fileHandle.write(string+"\n")
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
    resultFile = open("result.csv","w+")
    defaultResolver = getDefaultResolver()
    allDomains = []
    allTrails = []
    allDnsServers = []

    print "using "+defaultResolver+" as default resolver"

    for thisDomain in domainListFile:
        allDomains.append(thisDomain)

    for thisServer in dnsListFile:
        allDnsServers.append(thisServer)

    dnsListFile.close()
    domainListFile.close()

    dup = allDomains[:]
    for i in range(iterations):
        allDomains = allDomans + dup

    for i in allDomains:
        allTrails.append(Trail(i))

    random.shuffle(allTrails)

    for trail in allTrails:
        sleep(trail.waitTime)
        if(trail.ifReplicate):
            tempDNSFile = tempfile.NamedTemporaryFile(delete=False)
            dnsList = getRandomDnsList(allDnsServers,trail.numReps)
            for i in dnsList:
                tempDNSFile.write(i+"\n")
            tempDNSFile.close()

            proxy = subprocess.Popen([proxyBin,'-f',tempDNSFile.name])
            setResolver("127.0.0.1")
            sleep(0.1)
            runtime = timedExecute(trail.command)
            assert(proxy.returncode == None)
            writeResult(trail,runtime,resultFile)
            proxy.send_signal(SIGQUIT)
            os.remove(tempDNSFile.name)
        else:
            setResolver(defaultResolver)
            runtime = timedExecute(trail.command)
            writeResult(trail,runtime,resultFile)

    resultFile.close()
    setResolver(defaultResolver)
    
    
if(__name__ == '__main__'):
    main()
