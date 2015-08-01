#!/bin/bash
nprof=10000

cat 9serv.dns > servers.list
grep nameserver /etc/resolv.conf|cut -d' ' -f2|grep '^[0-9]' >> servers.list
python rankservers-profile.py $nprof &
python rankservers-client.py $nprof >/dev/null
cat profile.dat
