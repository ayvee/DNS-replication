#!/usr/bin/env python
import awis
from xml.etree import ElementTree
import os
import sys

class QueryEngine(object):
	def __init__(self):
		self.api = awis.AwisApi(os.environ['AWS_ACCESS_KEY'], os.environ['AWS_SECRET_KEY'])

	def pageviews(self, domain):
		"""retrieve Alexa's "pageviews" statistic for the last 1 month"""
		tree = self.api.url_info(domain, "UsageStats")
		prefix = self.api.NS_PREFIXES["awis"]
		for stat in tree.findall('.//{%s}UsageStatistic' % prefix):
			nmonths = stat.find("./{%s}TimeRange/{%s}Months" % (prefix, prefix))
			if nmonths != None and nmonths.text == '1' :
				def findstat(xml, statname):
					node = xml.find('./{%s}%s/{%s}PerMillion/{%s}Value' % (prefix, statname, prefix, prefix))
					if node is None:
						raise Exception("Could not find stat %s in %s" % (statname, xml))
					return float(node.text.replace(',', '')) # the replace is because Alexa returns comma separated values, which Python doesn't know how to parse
				return {"pageviews": findstat(stat, "PageViews"), "reach": findstat(stat, "Reach")}

engine = QueryEngine()
with open("client/alexa-top1000stats.tsv", 'w') as outf:
	outf.write('#website\tpageviews\treach\n')
	with open("client/top1000website.txt") as inf:
		for line in inf:
			website = line.strip()
			try:
				stats = engine.pageviews(website)
				output = "%s\t%s\t%s\n" % (website, stats['pageviews'], stats['reach'])
			except:
				print >> sys.stderr, "WARNING: trouble processing website %s, discarding" % website
			else:
				outf.write(output)
				print output,
