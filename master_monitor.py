#!/usr/bin/env python3
import os
import time
import requests
import paramiko
import subprocess
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import json 

import config

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# If using password-based SSH instead of a key, set config.SSH_KEY_PATH = None in config.py.
# SSH_PASSWORD = None  # e.g. "your-ssh-password" if not using key-based auth

# Track uptime to detect unexpected reboots
last_uptime = {}
# Track when a server was first detected down
down_since = {}

LAST_UPTIME_FILE = "last_uptime.json"
DOWN_SINCE_FILE = "down_since.json"

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

def load_down_since():
    """Load down_since values from a JSON file."""
    if os.path.exists(DOWN_SINCE_FILE):
        try:
            with open(DOWN_SINCE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_down_since(data):
    """Save down_since values to a JSON file."""
    try:
        with open(DOWN_SINCE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[Error] Failed to save down_since data: {e}")
        
def send_discord_alert(message: str):
    """
    Send an alert to Discord, prefixing the message with
    a timestamp in Hong Kong time (UTC+8).
    """
    if not DISCORD_WEBHOOK_URL:
        print("[Warning] DISCORD_WEBHOOK_URL not set. Skipping alert.")
        return

    # Get Hong Kong time
    HK_TZ = timezone(timedelta(hours=8))
    now_str = datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    data = {"content": f"[{now_str}] {message}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
    except Exception as e:
        print(f"[Error] Failed to send alert to Discord: {e}")

def run_local_command(command: str) -> str:
    """
    Runs a shell command locally using subprocess.
    Returns stdout as a string.
    Raises an exception on failure.
    """
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )
    return result.stdout.strip()

def run_ssh_command(server_addr: str, command: str) -> str:
    """
    Runs a command on a remote server via SSH, returns stdout as a string.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        keypath = config.SSH_KEY_PATH
        if keypath and os.path.isfile(os.path.expanduser(keypath)):
            client.connect(
                hostname=server_addr,
                username=config.SSH_USERNAME,
                key_filename=os.path.expanduser(keypath),
                look_for_keys=False,
                timeout=5
            )
        else:
            client.connect(
                hostname=server_addr,
                username=config.SSH_USERNAME,
                # password=SSH_PASSWORD,
                timeout=5
            )
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode("utf-8").strip()
        return output
    finally:
        client.close()

def run_command(server_name: str, server_addr: str, command: str) -> str:
    """
    Decide whether to run a local command (if server_name == config.CURRENT_SERVER_NAME)
    or run an SSH command (otherwise).
    """
    if server_name == config.CURRENT_SERVER_NAME:
        # Run locally
        return run_local_command(command)
    else:
        # Run via SSH
        return run_ssh_command(server_addr, command)

def is_server_reachable(name: str, address: str) -> bool:
    """
    Check if a server is reachable by attempting to run 'uptime'.
    """
    try:
        _ = run_command(name, address, "uptime")
        return True
    except:
        return False

def get_gpu_processes(name: str, address: str):
    """
    Returns a list of dicts with GPU processes:
      [
        {
          "pid": <pid>,
          "username": <linux user>,
          "process_name": <process name>,
          "gpu_mem_mb": <GPU memory usage in MB>
        },
        ...
      ]
    """
    results = []
    try:
        processes_str = run_command(
            name, 
            address, 
            "nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader,nounits"
        )
        lines = [line.strip() for line in processes_str.split('\n') if line.strip()]
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 3:
                continue
            pid_str, proc_name, gpu_mem_str = parts

            # Get username for this PID
            username = "unknown"
            try:
                user_str = run_command(name, address, f"ps -o user= -p {pid_str}")
                if user_str:
                    username = user_str.strip()
            except:
                pass

            results.append({
                "pid": pid_str,
                "username": username,
                "process_name": proc_name,
                "gpu_mem_mb": gpu_mem_str
            })
    except:
        pass
    return results

def get_temperatures(name: str, address: str) -> dict:
    """
    Retrieve CPU and GPU temperatures from the server.
    """
    temperatures = {"cpu": 0.0, "gpu": 0.0}
    # CPU
    try:
        cpu_temp_str = run_command(name, address, "sensors | grep 'Package id 0:' | awk '{print $4}'")
        if cpu_temp_str.startswith('+'):
            cpu_temp_str = cpu_temp_str[1:]
        temperatures["cpu"] = float(cpu_temp_str.replace('°C', '').strip())
    except:
        pass

    # GPU
    try:
        gpu_temp_str = run_command(name, address, "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits")
        gpu_temps = [float(x) for x in gpu_temp_str.split('\n') if x.strip()]
        if gpu_temps:
            temperatures["gpu"] = max(gpu_temps)
    except:
        pass

    return temperatures

def get_system_uptime(name: str, address: str) -> float:
    """Return the server's uptime in seconds."""
    try:
        output = run_command(name, address, "cat /proc/uptime")
        return float(output.split()[0])
    except Exception as e:
        print(f"[Error] Failed to get uptime for {name}: {e}")
        return 0.0

def monitor():
    """Check each server for temperature, unexpected reboots, and downtime."""
    global last_uptime
    last_uptime = load_last_uptime() 
    down_since = load_down_since()
    for server in config.SERVERS:
        server_name = server["name"]
        server_addr = server["address"]

        # 1) Check if server is up
        reachable = is_server_reachable(server_name, server_addr)
        if not reachable:
            if server_name not in down_since:
                down_since[server_name] = datetime.now().timestamp()
                save_down_since(down_since)
                send_discord_alert(f":x: **{server_name}** is down!")
            else:
                # Calculate how long it's been down
                down_time = datetime.now().timestamp() - down_since[server_name]
                # if server_name != "hakao": # 
                send_discord_alert(f":warning: **{server_name}** has been down for {int(down_time)} seconds!")
            continue
        else:
            # If server was previously down but now up, notify and remove from down_since
            if server_name in down_since:
                down_time = datetime.now().timestamp() - down_since[server_name]
                send_discord_alert(f":white_check_mark: **{server_name}** is back up after {int(down_time)} seconds!")
                del down_since[server_name]
                save_down_since(down_since)
                
        # 2) Temperature checks
        temps = get_temperatures(server_name, server_addr)
        # CPU
        if temps["cpu"] > config.CPU_TEMP_THRESHOLD:
            send_discord_alert(
                f":hot_face: **{server_name}** CPU temp {temps['cpu']}°C exceeded threshold ({config.CPU_TEMP_THRESHOLD}°C)!"
            )
        # GPU
        if temps["gpu"] > config.GPU_TEMP_THRESHOLD:
            gpu_procs = get_gpu_processes(server_name, server_addr)
            if not gpu_procs:
                info_str = "No GPU processes found."
            else:
                lines = []
                for proc in gpu_procs:
                    lines.append(
                        f"- PID {proc['pid']}, User: {proc['username']}, Process: {proc['process_name']}, GPU Mem: {proc['gpu_mem_mb']} MB"
                    )
                info_str = "\n".join(lines)

            send_discord_alert(
                f":hot_face: **{server_name}** GPU temp {temps['gpu']}°C exceeded threshold ({config.GPU_TEMP_THRESHOLD}°C)!\n"
                f"**Processes using the GPU:**\n{info_str}"
            )


        # 3) Check for unexpected reboots (uptime)
        current_uptime = get_system_uptime(server_name, server_addr)
        if server_name in last_uptime:
            if current_uptime + 300 < last_uptime[server_name]:  # If uptime is less, the server rebooted
                send_discord_alert(f":warning: **{server_name}** rebooted unexpectedly!")
        last_uptime[server_name] = current_uptime
        save_last_uptime(last_uptime)
        
def main_loop():
    # while True:
        monitor()
        # time.sleep(60)

if __name__ == "__main__":
    main_loop()