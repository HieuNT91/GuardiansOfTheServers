# GuardiansOfTheServers
The One Scripts to Rule them all


## install ubuntu package

```bash
sudo apt install lm-sensors
```

## start service

```bash
sudo cp services/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable master_monitor.timer
sudo systemctl start master_monitor.timer
# or 
sudo systemctl enable monitor_sashimi.timer
sudo systemctl start monitor_sashimi.timer
```