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
import bisect
import abc
import Queue
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

import logging
logging.basicConfig(level = logging.DEBUG, format = "[%(asctime)s] %(levelname)s: %(message)s")
log = logging.getLogger()

# we will load no more than one page every minTrialDuration seconds to avoid
# overloading the local DNS server
minTrialDuration = 0
outputFilenames = "results/%sresult%d.csv"
proxyFilenames = "results/proxy%d.csv"
basedir = os.path.dirname(os.path.abspath(__file__))
proxyBin = basedir + "/../proxy/proxy"
proxyLockfile = basedir + "/../proxy/proxy_active"
alexaStatsFile = basedir + "/alexa-top1000stats.tsv"


def getDefaultBrowser():
	#return webdriver.Firefox()
	return webdriver.Chrome('./chromedriver')

def getURL(website):
	if website.startswith('http'):
		return website
	else:
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

class Timeout:
	def __init__(self, seconds):
		self.seconds = seconds

	def handle_timeout(self, signum, frame):
		raise Exception('Function timed out')

	def __enter__(self):
		signal.signal(signal.SIGALRM, self.handle_timeout)
		signal.alarm(self.seconds)

	def __exit__(self, type, value, traceback):
		signal.alarm(0)

def getDownloadTimeWebdriver(url):
	downloadTimeoutSec = 60
	succeeded = False
	downloadTime = 0
	numRetries = 0
	log.info("Downloading "+str(url))
	#start = datetime.now()
	driver = None
	try:
		def getRandomLink():
			links = driver.find_elements_by_partial_link_text('')
			if not links:
				return None
			for i in xrange(10): # FIXME?
				ret = random.choice(links).get_attribute('href')
				if ret is not None and ret.startswith('http'):
					return ret
			else:
				return None
		with Timeout(2 * downloadTimeoutSec):
			driver = getDefaultBrowser()
			time.sleep(5) # for browser init
			driver.get(url)
			wait = WebDriverWait(driver, downloadTimeoutSec, poll_frequency=5).\
					until(lambda drv: drv.execute_script("return document.readyState") == "complete")
			if not wait:
				return downloadTimeoutSec, getRandomLink()
			else:
				exectime = driver.execute_script("return performance.timing.loadEventEnd - performance.timing.navigationStart")
				return float(exectime) * 1e-3, getRandomLink()
	except Exception as e:
		log.error(e)
		return downloadTimeoutSec, None
	finally:
		if driver != None:
			driver.quit()
		subprocess.call(["pkill", "-9", "-f", "chrome"])
	#end = datetime.now()
	#diff = end - start
	#downloadTime = diff.seconds * 1000 * 1000 + diff.microseconds

def setResolver(resolver):
	rv = os.system("echo \"nameserver "+str(resolver)+"\" > /etc/resolv.conf")
	if rv != 0:
		log.error("failed to set resolver to "+str(resolver))
		exit(1)

def getDnsList(localServer, publicServers, numNeeded):
	random.shuffle(publicServers)
	return ([localServer] + publicServers)[:numNeeded]

# TODO: may want to make this a context manager instead of the explicit done()
class ResultsCollector:
	def __init__(self, maxNumReps = None, outputFilenameFormat = outputFilenames):
		self.outputFilenameFormat = outputFilenameFormat
		#if maxNumReps is not None:
		#	# truncate all output files
		#	for n in xrange(1, maxNumReps+1):
		#		with open(self.outputFilenameFormat % n, 'w'):
		#			pass

	def update(self, numReps, website, time, file_prefix = ''):
		with open(self.outputFilenameFormat % (file_prefix, numReps), 'a') as outf:
			outf.write("{website},{time}\n".format(**locals()))

	def done(self):
		pass

class Proxy:
	def __init__(self, proxyBin, proxyLockfile, dnsServers, stdoutFD, stderrFile):
		self.proxyBin = proxyBin
		self.proxyLockfile = proxyLockfile
		self.dnsServers = dnsServers
		self.stdoutFD = stdoutFD
		self.stderrFile = stderrFile
		self.process = None

	def __enter__(self):
		self.dnsFile = dnsFile = tempfile.NamedTemporaryFile(delete=False)
		dnsFile.write("\n".join(self.dnsServers) + '\n')
		dnsFile.close()

		try:
			setResolver("127.0.0.1")
			log.debug("%s -f %s" % (self.proxyBin, dnsFile.name))
			self.stderrFD = open(self.stderrFile, 'a')
			self.process = subprocess.Popen([self.proxyBin,'-f', dnsFile.name], stdout = self.stdoutFD, stderr = self.stderrFD)
		except:
			os.unlink(dnsFile.name)
			raise
		return self

	def waitTillSetUp(self):
		"wait for proxy to come up"
		while True:
			try:
				with open(self.proxyLockfile, 'r') as lockf:
					content = lockf.readline().split(',')
					startTime = int(content[0])
					replication = int(content[1])
					if replication == len(self.dnsServers):
						break
			except IOError as e:
				time.sleep(0.5)

	def __exit__(self, typ, value, traceback):
		try:
			if self.stderrFD is not None:
				self.stderrFD.close()
			process = self.process
			if process.returncode is not None:
				log.error("Proxy process died before we were done with it")
			else:
				os.kill(process.pid,signal.SIGQUIT)
				process.wait()
		finally:
			os.unlink(self.dnsFile.name)

################################################################################

class AlexaStats(object):
	def __init__(self):
		self.websites = []
		self.cdf = []
		with open(alexaStatsFile) as inf:
			cum = 0.
			for line in inf:
				if not line or line[0] == '#':
					continue
				vals = line.strip().split()
				website = vals[0]
				cum += float(vals[2])
				self.websites.append(website)
				self.cdf.append(cum)
			for i in xrange(len(self.cdf)):
				self.cdf[i] = self.cdf[i] / cum

	def random_unweighted(self):
		return random.choice(self.websites)

	def random_weighted(self):
		rand = random.random()
		i = bisect.bisect(self.cdf, rand)
		if i == len(self.cdf):
			i = len(self.cdf) - 1
		return self.websites[i]

class Chooser(object):
	__metaclass__ = abc.ABCMeta

	def __init__(self):
		self.alexa = AlexaStats()

	@abc.abstractmethod
	def get_replevel(self, trialnum):
		return

	@abc.abstractmethod
	def get_interarrival(self, trialnum):
		return

	@abc.abstractmethod
	def get_website(self, trialnum, randomPrevLink):
		"randomPrevLink is a random link on the previous webpage"
		return

	def get_fileprefix(self):
		return ''

class RandomChooser(Chooser):
	def __init__(self, numServers):
		super(RandomChooser, self).__init__()
		self.numServers = numServers

	def get_replevel(self, trialnum):
		return random.randint(1, self.numServers)

	def get_interarrival(self, trialnum):
		return 0

	def get_website(self, trialnum, randomPrevLink):
		return self.alexa.random_unweighted()

class RealisticChooser(Chooser):
	def __init__(self, numServers, batchSize):
		super(RealisticChooser, self).__init__()
		assert numServers == 10
		#self.numServers = numServers
		self.batchSize = batchSize

	def get_replevel(self, trialnum):
		if trialnum % self.batchSize == 1:
			#self.replevel = random.randint(1, self.numServers)
			self.replevel = random.choice([1, 2, 3, 5, 10])
		return self.replevel

	def get_interarrival(self, trialnum):
		return random.lognormvariate(-0.495204, 2.7731)

	def get_website(self, trialnum, randomPrevLink):
		return self.alexa.random_weighted()

class LinkFollowChooser(Chooser):
	def __init__(self, numServers, batchSize):
		super(LinkFollowChooser, self).__init__()
		assert numServers == 10
		self.batchSize = batchSize

	def get_replevel(self, trialnum):
		if trialnum % self.batchSize == 1:
			#self.replevel = random.randint(1, self.numServers)
			self.replevel = random.choice([1, 2, 5])
			self.followProbability = random.choice([0.2, 0.4, 0.6, 0.8, 1.0])
		return self.replevel

	def get_interarrival(self, trialnum):
		return 0

	def get_website(self, trialnum, randomPrevLink):
		if random.random() < self.followProbability and randomPrevLink is not None:
			return randomPrevLink
		else:
			return self.alexa.random_weighted()

	def get_fileprefix(self):
		return 'p%s_' % self.followProbability

def main():
	if len(sys.argv) != 3:
		print "SYNTAX: %s <dns_servers_list> <experiment>" % sys.argv[0]
		exit(2)

	if os.getuid() != 0:
		print "Needs root permission"
		exit()

	DEVNULL = open(os.devnull,'wb')

	allDnsServers = []
	publicDnsServers = []

	defaultResolver = getDefaultResolver()
	log.info("Default resolver: "+defaultResolver)
	allDnsServers.append(defaultResolver)

	dnsListFile = sys.argv[1]
	with open(dnsListFile) as inf:
		for thisServer in inf:
			publicDnsServers.append(thisServer.rstrip())
			allDnsServers.append(thisServer.rstrip())

	experiment = sys.argv[2]
	if experiment == "random":
		chooser = RandomChooser(len(allDnsServers))
	elif experiment == "realistic":
		chooser = RealisticChooser(len(allDnsServers), 50)
	elif experiment == "linkfollow":
		chooser = LinkFollowChooser(len(allDnsServers), 50)
	else:
		raise Exception("Unrecognized experiment "  + experiment)

	resultsCollector = None
	randomPrevLink = None
	try:
		resultsCollector = ResultsCollector(len(allDnsServers))
		trialnum = 0
		while True:
			trialnum += 1
			currTime = datetime.now()
			
			numReps = chooser.get_replevel(trialnum)
			website = chooser.get_website(trialnum, randomPrevLink)
			def doLookup(numReps, website):
				log.info('loading %s with %s-way DNS replication' % (website, numReps))
				runtime, randomPrevLink = getDownloadTimeWebdriver(getURL(website))
				log.info('load time %s, random link %s' % (runtime, randomPrevLink))
				#runtime = getDownloadTimeWget(getURL(allDomains[trial.websiteID]))
				resultsCollector.update(numReps, website, runtime, chooser.get_fileprefix())
				return randomPrevLink
			#if(numReps > 1):
			if(numReps > 0): # FIXME
				dnsServers = getDnsList(defaultResolver, publicDnsServers, numReps)
				log.debug("%d servers: %s; allDnsServers = %s", numReps, dnsServers, allDnsServers)
				with Proxy(proxyBin, proxyLockfile, dnsServers, stdoutFD = DEVNULL, stderrFile = proxyFilenames % numReps) as proxy:
					proxy.waitTillSetUp()
					randomPrevLink = doLookup(numReps, website)
			else:
				setResolver(defaultResolver)
				doLookup(numReps, website)

			#nextTrialAt = currTime + timedelta(seconds = minTrialDuration)
			#sleepDuration = (nextTrialAt - datetime.now()).total_seconds()
			sleepDuration = chooser.get_interarrival(trialnum)
			if sleepDuration > 0:
				log.info("Sleeping for %s seconds" % sleepDuration)
				time.sleep(sleepDuration)
	finally:
		setResolver(defaultResolver)
		if resultsCollector is not None:
			resultsCollector.done()
	DEVNULL.close()

if __name__ == '__main__':
	main()
