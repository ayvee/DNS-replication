import os
import sys
import time
from datetime import datetime

cmd = "/usr/bin/wget --timeout=8 -e robots=off -U \"Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0\" --page-requisites --no-check-certificate "

iterations = 100

def getDefaultResolver():
    resolvFile = open("/etc/resolv.conf",'r')
    for line in resolvFile:
        line = line.replace('\n','').strip()
        if line[0] == '#' or len(line) < len("nameserver "):
            continue
        if line[:11] == "nameserver ":
            return line[11:]

def download(website):
    assert len(website)>0
    start = datetime.now()
    os.system(cmd+website+" &>/dev/null")
    end = datetime.now()
    diff = end - start
    os.system("for i in $(ls -d */); do sudo rm -rf $i; done")
    return diff.seconds*1000000+diff.microseconds

def downloadAll(fileHandle,outputHandle):
    fileHandle.seek(0,0)
    while True:
        website = fileHandle.readline().replace('\n','').strip()
        if len(website) == 0:
            break
        runtime = download(website)
        outputHandle.write(website+","+str(runtime)+"\n")
        print "download time of "+website+" is "+str(runtime)+"\n"
        time.sleep(0.5)

def setResolver(resolver):
    rv = os.system("sudo echo \"nameserver "+str(resolver)+"\" > /etc/resolv.conf")
    if rv != 0:
        print "failed to set resolver to "+str(resolver)
        exit(1)

def main():
    if len(sys.argv) != 2:
        print "needs file name"
        exit()
    defaultResolver = getDefaultResolver()
    print "using "+defaultResolver+" as default resolver"
    assert len(defaultResolver) != 0
    domainListFile = open(sys.argv[1])
    for i in range(0,iterations):
        setResolver(defaultResolver)
        output = open("result_no_rep"+str(i),'w')
        downloadAll(domainListFile, output)
        output.close()

        time.sleep(60)

        setResolver("127.0.0.1")
        output = open("result_with_rep"+str(i),'w')
        downloadAll(domainListFile, output)
        output.close()

        time.sleep(60)

    domainListFile.close()
    setResolver(defaultResolver)

if __name__ == '__main__':
    main()
