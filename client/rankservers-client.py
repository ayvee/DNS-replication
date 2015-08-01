import subprocess
import time
import random
import sys

def lookup(name = None, fil = None):
    ip = '127.0.0.1'
    port = 50053
    cmd = 'dig @%s -p %d ' % (ip, port)
    if name is not None:
        cmd = cmd + name
    elif fil is not None:
        cmd = cmd + '-f ' + fil
    subprocess.call(cmd, shell = True)

if len(sys.argv) != 2:
    print >> sys.stderr, "SYNTAX: %s <nvals>" % sys.argv[0]
    sys.exit(2)
nvals = int(sys.argv[1])

all_names = [l.strip() for l in open('top1000website.txt')]
targets = random.sample(all_names, nvals)
for i in xrange(nvals):
    lookup(random.coice(all_names))
    time.sleep(5)
