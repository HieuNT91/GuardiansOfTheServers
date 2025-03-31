#!/usr/bin/env python3

import os
import time
import requests
import paramiko
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import config
import json

LAST_UPTIME_FILE = "last_uptime.json"

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# SSH_PASSWORD = None  # or "your-ssh-password" if not using key-based auth

def load_last_uptime():
    """Load last uptime values from a JSON file."""
    if os.path.exists(LAST_UPTIME_FILE):
        try:
            with open(LAST_UPTIME_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_last_uptime(data):
    """Save last uptime values to a JSON file."""
    try:
        with open(LAST_UPTIME_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[Error] Failed to save last uptime data: {e}")


def send_discord_alert(message: str):
    """
    Send an alert to Discord, including a timestamp in Hong Kong time (UTC+8).
    """
    if not DISCORD_WEBHOOK_URL:
        print("[Warning] DISCORD_WEBHOOK_URL not set. Skipping alert.")
        return

    HK_TZ = timezone(timedelta(hours=8))
    now_str = datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data = {"content": f"[{now_str}] {message}"}

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
    except Exception as e:
        print(f"[Error] Failed to send alert to Discord: {e}")

def is_sashimi_reachable() -> bool:
    """
    Attempt to SSH into 'sashimi'. If we can run 'uptime' successfully, it's reachable.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        keypath = config.SSH_KEY_PATH
        if keypath and os.path.isfile(os.path.expanduser(keypath)):
            client.connect(
                hostname="rtx_sashimi",
                username=config.SSH_USERNAME,
                key_filename=os.path.expanduser(keypath),
                look_for_keys=False,
                timeout=5
            )
        else:
            client.connect(
                hostname="rtx_sashimi",
                username=config.SSH_USERNAME,
                # password=SSH_PASSWORD,
                timeout=5
            )
        stdin, stdout, stderr = client.exec_command("uptime")
        stdout.read()  # just to ensure no exception is thrown
        return True
    except:
        return False
    finally:
        client.close()

def monitor_sashimi():
    reachable = is_sashimi_reachable()
    if not reachable:
        send_discord_alert(":warning: **sashimi** appears to be down! (Checked from **hakao**).")

def main_loop():
    # while True:
        monitor_sashimi()
        # time.sleep(60)

if __name__ == "__main__":
    main_loop()