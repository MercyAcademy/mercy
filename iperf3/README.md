# Setup to run iperf3

Want to run it perpetually on the linux box.

Systemctrld instructions:

https://www.digitalocean.com/community/tutorials/how-to-configure-a-linux-service-to-start-automatically-after-a-crash-or-reboot-part-1-practical-examples#auto-starting-services-with-systemd

```
sudo -s
yum install -y iperf3

cd /usr/lib/systemd/system
cp httpd.service iperf3.service

Edit it to:

[Unit]
Description=Mercy iperf3 service
After=network.target remote-fs.target nss-lookup.target

[Service]
Type=notify
Environment=LANG=C

ExecStart=/usr/bin/iperf3 -s
KillSignalSIGHUP
Restart=always

[Install]
WantedBy=multi-user.target

systemctl daemon-reload
systemctl enable iperf3

# You may have to hit ctrl-c to get this to complete,
# but a "ps" should show that iperf3 is still running
systemctl start iperf3
```

A reboot should show that it is still running.
