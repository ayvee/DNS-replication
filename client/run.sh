#!/bin/bash
if [ $# -ne 1 ]
then
	echo "SYNTAX: $0 <experiment>"
	exit 2
fi
while [ 1 ]
do
	sudo ./full-random.py ranked.dns $1
done
