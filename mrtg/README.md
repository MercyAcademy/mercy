yum -y install httpd mrtg net-snmp net-snmp-utils

systemctl start httpd.service
systemctl enable httpd.service

Edit /etc/snmp/snmpd.conf per
https://www.techtransit.org/mrtg-installation-on-centos-7-rhel-7-fedora-and-linux/

sudo systemctl start snmpd.service
sudo systemctl enable snmpd.service

snmpwalk -v2c -c techtransit localhost system

sudo -s

cfgmaker --snmp-options=:::::2 --ifref=descr --ifdesc=descr --global 'WorkDir: /var/www/mrtg' techtransit@10.0.2.15 > /etc/mrtg/mrtg-new.cfg

# Compare mrtg-new.cfg to mrtg.cfg -- see if it's worthwhile.

indexmaker --columns=1 /etc/mrtg/mrtg.cfg > /var/www/mrtg/index.html
