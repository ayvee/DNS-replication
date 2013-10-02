#!/bin/bash

sudo cp /etc/resolv.conf ./resolv.conf.bak

sudo echo "nameserver 127.0.0.1" > /etc/resolv.conf

python agent.py top100website.txt
mv result result100_rep5_1.txt

sleep 120

sudo cp ./resolv.conf.bak /etc/resolv.conf

python agent.py top100website.txt
mv result result100_ori_1.txt

sleep 120

sudo echo "nameserver 127.0.0.1" > /etc/resolv.conf

python agent.py top100website.txt
mv result result100_rep5_2.txt

sleep 120

sudo cp ./resolv.conf.bak /etc/resolv.conf

python agent.py top100website.txt
mv result result100_ori_2.txt

sleep 120

sudo echo "nameserver 127.0.0.1" > /etc/resolv.conf

python agent.py top100website.txt
mv result result100_rep5_3.txt

sleep 120

sudo cp ./resolv.conf.bak /etc/resolv.conf

python agent.py top100website.txt
mv result result100_ori_3.txt

sleep 120

sudo echo "nameserver 127.0.0.1" > /etc/resolv.conf

python agent.py top100website.txt
mv result result100_rep5_4.txt

sleep 120

sudo cp ./resolv.conf.bak /etc/resolv.conf

python agent.py top100website.txt
mv result result100_ori_4.txt

sleep 120

sudo echo "nameserver 127.0.0.1" > /etc/resolv.conf

python agent.py top100website.txt
mv result result100_rep5_5.txt

sleep 120

sudo cp ./resolv.conf.bak /etc/resolv.conf

python agent.py top100website.txt
mv result result100_ori_5.txt

