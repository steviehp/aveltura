import subprocess
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

VEL_PORT = os.getenv("VEL_PORT", "8001")
CHECK_INTERVAL = 60  # check every 60 seconds

def check_vel():
    try:
        r = requests.get(f"http://localhost:{VEL_PORT}/health", timeout=5)
        return r.status_code == 200
    except:
        return False

def restart_vel():
    print("Vel is down, restarting...")
    subprocess.run(["sudo", "systemctl", "restart", "vel"])

while True:
    if not check_vel():
        restart_vel()
    else:
        print("Vel is healthy")
    time.sleep(CHECK_INTERVAL)
