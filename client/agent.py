import sys
import os
import urllib2
import socket
import smtplib
import time
import random
from datetime import datetime

cmd = "/usr/bin/wget --timeout=8 -e robots=off -U \"Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0\" --page-requisites --no-check-certificate "

def run(website):
	start = datetime.now()
	os.system(cmd + str(website) + " &>/dev/null")
	end = datetime.now()
	diff = end-start
	return diff.seconds*1000 + diff.microseconds/1000

def main():
	if len(sys.argv) != 2 :
		print "needs file name"
		exit()
	domainList = open(sys.argv[1])
	currFile = open("./result", 'w')
	while True :
		curr = domainList.readline()
		curr = curr.replace('\n', '')
		curr = curr.strip()
		if len(curr)==0:
			break
		runTime = run(curr)
		currFile.write(curr+"\t"+str(runTime)+"\n")
		print curr+"\t"+str(runTime)
		time.sleep(1)
	currFile.close()

if __name__ == '__main__':
	main()
