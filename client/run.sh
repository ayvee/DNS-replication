#!/bin/bash
if [ $# -ne 1 ]
then
	echo "SYNTAX: $0 <experiment>"
	exit 2
fi
while [ 1 ]
do
	sudo ./full-random.py 9serv.dns $1
done
