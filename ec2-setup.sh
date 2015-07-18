#!/bin/bash
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list'
sudo apt-get update
sudo apt-get -y install gnome-core gnome-session-fallback vnc4server google-chrome-stable python-setuptools make g++ git expect
#sudo easy_install pip
#sudo pip install selenium
sudo easy_install selenium

/usr/bin/expect <<EOF
spawn vncpasswd
expect "Password:"
send "crump3ts\n"
expect "Verify:"
send "crump3ts\n"
expect eof
exit
EOF
vncserver -kill :0
vncserver :0 --BlacklistTimeout=0

cd $HOME
git clone https://github.com/ayvee/DNS-replication.git code
cd code/proxy
make
cd $HOME
mkdir code/client/results
