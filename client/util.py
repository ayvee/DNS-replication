import functools, inspect

def copy_args_into_self(function):
    """Suppose the function is defined as f(self, a, b, c). Then this decorator
    replaces f with a wrapper that, when it is called with arguments
    (self, u, v, w), sets
        self.a = u
        self.b = v
        self.c = w
    before actually calling f(self, u, v, w)"""
    @functools.wraps(function)
    def wrapper(*pos_args, **kw_args):
        argnames, _, _, defaults = inspect.getargspec(function)
        if not defaults:
            defaults = tuple()
        args = dict(zip(argnames, pos_args + defaults))
        if kw_args:
            args.update(kw_args)
        self = args[argnames[0]]
        del args[argnames[0]]
        self.__dict__.update(args)
        return function(*pos_args, **kw_args)
    return wrapper

def maxindex(iterable, key = lambda x: x):
    "Return (index, value) of the largest element in iterable"
    return max(enumerate(iterable), key = lambda (i, v): key(v))

def minindex(iterable, key = lambda x: x):
    "Return (index, value) of the smallest element in iterable"
    return min(enumerate(iterable), key = lambda (i, v): key(v))

class Averager(object):
    def __init__(self):
        self.T = 0
        self.avg = 0.0

    def update(self, val, tstep = 1):
        self.avg = (self.T * self.avg + tstep * val) / (self.T + tstep)
        self.T += tstep

    def get(self):
        return self.avg

class CdfGenerator(object):
    def __init__(self, minval = None, maxval = None, nbins = 1000):
        self.nbins = nbins
        self.bins = [0] * nbins
        self.nvals = 0
        if minval is not None and maxval is not None:
            self.have_range = True
            self.minval = minval
            self.maxval = maxval
        else:
            self.have_range = False
            self.all_values = []
        self.empty = True
        self.cdf = []

    def __update_bins(self, val):
        # If f(k) = minval + k * (maxval - minval) / nbins, we must have
        # f(binnum) <= val < f(binnum + 1)
        binnum = int((val - self.minval) * float(self.nbins) / (self.maxval - self.minval))
        binnum = max(binnum, 0)
        binnum = min(binnum, self.nbins-1)
        self.bins[binnum] += 1
        
    def update(self, val):
        self.empty = False
        self.nvals += 1
        if self.have_range:
            self.__update_bins(val)
        else:
            self.all_values.append(val)

    def done(self):
        if self.empty:
            return
        if not self.have_range:
            if not self.all_values:
                return
            self.minval = min(self.all_values)
            self.maxval = max(self.all_values)
            if self.maxval == self.minval:
                return
            for val in self.all_values:
                self.__update_bins(val)
        endpoint = lambda k: self.minval + float(k) / self.nbins * (self.maxval - self.minval)
        bin_range = lambda k: (endpoint(k), endpoint(k+1))
        cumulative = 0
        vals = []
        for i, count in enumerate(self.bins):
            lv, rv = bin_range(i)
            cumulative += count
            cd = float(cumulative) / self.nvals
            vals.append((lv, rv, cd))
        self.cdf = vals
        return vals

    def lookup(self, percentile):
        if self.empty or not self.cdf:
            infty = 10**6
            return infty
        # binary search will be faster
        for lv, rv, cd in self.cdf:
            if cd >= percentile:
                return rv

    def to_string(self):
        return '\n'.join('{0[0]},{0[1]},{0[2]}'.format(c) for c in self.cdf) + '\n'

    def write_to(self, fil):
        open(fil, 'w').write(self.to_string())

if __name__ == "__main__":
    import sys
    c = CdfGenerator(sys.stdout, nbins = 8)
    c.update(1)
    c.update(1)
    c.update(1.75)
    c.update(5)
    c.done()
