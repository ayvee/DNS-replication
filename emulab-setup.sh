#!/bin/bash
if [ ! -b /dev/sdb1 ]
then
	sudo bash -c 'echo ",,83"|sfdisk /dev/sdb'
fi
sudo mke2fs -j /dev/sdb1
sudo mkdir -p /local/dns
sudo mount /dev/sdb1 /local/dns
sudo chown -R vulimir1:UIUCScheduling /local/dns
git clone https://github.com/ayvee/DNS-replication.git code
ln -s /proj/UIUCScheduling/dns/results /local/dns/code/proxy/client/results
cd /local/dns/code/proxy
make

wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
sudo apt-get update
sudo apt-get -y install gnome-core gnome-session-fallback vnc4server google-chrome-stable python-setuptools
#sudo easy_install pip
#sudo pip install selenium
sudo easy_install selenium
