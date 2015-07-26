#!/usr/bin/env python
import os, subprocess, sys
import pickle, json
from multiprocessing import Pool

basedir = os.path.dirname(os.path.abspath(__file__))

class Info(object):
	def __init__(self, group):
		self.group = group
		self.info_file = "%s/group_%s.info.json" % (basedir, group)
		self.load()

	def load(self):
		try:
			with open(self.info_file) as inf:
				self.info = json.load(inf)
		except:
			self.info = {}

	def dump(self):
		with open(self.info_file, 'w') as outf:
			jsons = json.dumps(self.info, sort_keys = True, indent = 4, separators = (',', ': '))
			print jsons
			outf.write(jsons)
			outf.write('\n')

	def create_instance(self, region):
		if region in self.info:
			raise Exception("instance already exists in %s" % region)
		# FIXME: check_output and use to update self.instances
		iid = subprocess.check_output(["%s/manage-ec2/create-instance" % basedir, region]).strip()
		self.info[region] = {'instance-id': iid}
		self.dump()
		#self.update_info()

	def kill_instance(self, region):
		if region not in self.info:
			raise Exception("instance doesn't exist in %s" % region)
		subprocess.call(["ec2-terminate-instances", "--region", region, self.info[region]['instance-id']])
		del self.info[region]
		self.dump()

	def update_info(self):
		for region, info in self.info.iteritems():
			try:
				for line in subprocess.check_output(["ec2-describe-instances", "--region", region]).split("\n"):
					vals = line.strip().split()
					if vals and vals[0] == "INSTANCE" and vals[1] == info['instance-id']:
						assert region == vals[10][:-1]
						print line
						self.info[region] = {
								'instance-id': vals[1],
								'hostname': vals[3],
								'security-group': vals[18]
								}
			except:
				continue
		self.dump()

	def run(self, cmd, args):
		try:
			func = getattr(self, cmd)
		except AttributeError:
			raise Exception("Invalid command %s" % cmd)
		else:
			func(*args)

	def vnc(self, region):
		if region not in self.info:
			raise Exception("no instance in region %s" % region)
		subprocess.call(["open", "vnc://" + self.info[region]['hostname']])

	def ssh(self, region, *args):
		if region not in self.info:
			raise Exception("no instance in region %s" % region)
		subprocess.call(["ssh", "-oStrictHostKeyChecking=no", "-lubuntu", self.info[region]['hostname']] + list(args))

	def scp(self, region, *args):
		if region not in self.info:
			raise Exception("no instance in region %s" % region)
		args = list(args) # convert from tuple
		for i in xrange(len(args)):
			args[i] = args[i].replace("amhost", "ubuntu@" + self.info[region]['hostname'])
		subprocess.call(["scp", "-oStrictHostKeyChecking=no"] + args)

	def setup_firewall(self, region):
		if region not in self.info:
			raise Exception("no instance in region %s" % region)
		for port in 22, 5900:
			subprocess.call(["ec2-authorize", self.info[region]['security-group'], "-P", "tcp", "-p", str(port), "-s", "0.0.0.0/0", "--region", region])

	def setup_host(self, region):
		if region not in self.info:
			raise Exception("no instance in region %s" % region)
		self.scp(region, "ec2-setup.sh", "amhost:~")
		self.ssh(region, "./ec2-setup.sh")

	def setup(self, region):
		self.setup_firewall(region)
		self.setup_host(region)

	def print_regions(self):
		for region in sorted(self.info):
			print region


def syntax_error():
	print "SYNTAX: $0 <group> <cmd> [arg] [arg...]"
	sys.exit(2)

if __name__ == '__main__':
	if len(sys.argv) < 3:
		syntax_error()
	group = sys.argv[1]
	cmd = sys.argv[2]
	args = sys.argv[3:]

	info = Info(group)
	info.run(cmd, args)

#if cmd == "update_info":
#	info.update()
#elif cmd == "vnc":
#	info.vnc(sys.argv[2])
#elif cmd == "ssh":
#	info.ssh(sys.argv[2], sys.argv[3:])
#elif cmd == "scp":
#	info.scp(sys.argv[2], sys.argv[3:])
#elif cmd == "setup":
#	info.setup(sys.argv[2])
#elif cmd == "hostname":
#	info.hostname(sys.argv[2])
#else:
#	syntax_error()
