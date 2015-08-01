import socket, select
import sys
import datetime
now = datetime.datetime.now
import random
import collections
import util

#NOTE: throughout, each "option" is a list of DNS servers

errct = 0
response_timeout = 2

class SockInfo(object):
    def __init__(self, src, started_at):
        self.src = src
        self.started_at = started_at
        self.response_time = None

    def recvd(self, at):
        self.response_time = at - self.started_at

def new_request(option, serv, timeout = response_timeout):
    data, addr = serv.recvfrom(1024)
    newaddr = ('', addr[1]+1)
    newsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        newsock.bind(newaddr)
    except Exception, e:
        global errct
        errct += 1
        newsock.close()
        return None, None
    si = SockInfo(addr, now())
    newsock.settimeout(timeout)
    for server in option:
        newsock.sendto(data, (server, 53))
    return newsock, si

def reply(sock, si, serv):
    try:
        data, addr = sock.recvfrom(1024)
        si.recvd(now())
        serv.sendto(data, si.src)
    except socket.timeout:
        pass
    sock.close()
    return si.response_time

def update_stats(response_time_struct, mg, cg):
    if response_time_struct is None:
        response_time = response_timeout
    else:
        to_float = lambda delta: delta.seconds + delta.microseconds * 1e-6
        response_time = to_float(response_time_struct)
    mg.update(response_time)
    cg.update(response_time)

def run_server(port, options, nqueries = -1):
    host = ''
    serv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serv.bind((host, port))

    mgs = [util.Averager() for i in xrange(len(options))]
    cgs = [util.CdfGenerator() for i in xrange(len(options))]

    while nqueries != 0:
        if nqueries > 0: nqueries -= 1
        option_num = random.randint(0, len(options)-1)
        option = options[option_num]
        sock, si = new_request(option, serv)
        if sock is None: continue
        response_time_struct = reply(sock, si, serv)
        update_stats(response_time_struct, mgs[option_num], cgs[option_num])
        if nqueries % 100 == 0:
            print >> sys.stderr, '[%s] \t nqueries = %d' % (str(now()), nqueries)
    serv.close()

    for cg in cgs: cg.done()

    return mgs, cgs

def process_results(options, mgs, cgs):
    dat = open('profile.dat', 'w')
    dat.write("Server\tMean\t50th\t95th\t99th\t100th\n")
    for k, (option, mg, cg) in enumerate(zip(options, mgs, cgs)):
        dat.write("%s\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\n" % (option[0], mg.get(), cg.lookup(0.5), cg.lookup(0.95), cg.lookup(0.99), cg.lookup(1)))
    dat.close()
    ordered = sorted(enumerate(options), key = lambda (i, _): mgs[i].get())
    outf = open('ordered.servers.list', 'w')
    outf.write('\n'.join(option[0] for _, option in ordered))
    outf.write('\n')
    outf.close()

if len(sys.argv) != 2:
    print >> sys.stderr, "SYNTAX: %s <nvalues>" % sys.argv[0]
    sys.exit(2)
nvals = int(sys.argv[1])

servers = [line.strip() for line in open('servers.list')]
options = [[s] for s in servers]
mgs, cgs = run_server(50053, options, nvals)
process_results(options, mgs, cgs)

print 'Error counts: %d' % errct
