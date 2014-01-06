#!/usr/bin/python
import util
import sys
import math

timeout = 20

def write_cdf(inf, outf, linesep = None, colnum = None):
    stats = util.Statistics()
    for line in open(inf):
        if linesep is not None:
            val = float(line.strip().split(linesep)[colnum])
        else:
            val = float(line)
        if val > timeout:
            val = timeout
        stats.update(val)
    stats.done()
    stats.write_to(outf)

if __name__ == '__main__':
    dirname = "results"
    from glob import glob
    for inf in glob("%s/*csv" % dirname):
        print "Processing", inf
        write_cdf(inf = inf, linesep = ",", colnum = 1,
                  outf = inf[:-4] + ".cdf")
