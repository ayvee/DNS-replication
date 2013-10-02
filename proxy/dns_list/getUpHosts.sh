#!/bin/bash

for ip in $(cat $1 | cut -d, -f1)
do
	echo -n "Testing ${ip}..."
	dig @$ip +time=1 google.com &> /dev/null
	if [ $? -eq 0 ] 
	then
		echo $ip >> $2
		echo -e " \e[0;32mOK\e[00m"
	else
		echo -e " \e[0;31mNo response\e[00m"
	fi	
done
