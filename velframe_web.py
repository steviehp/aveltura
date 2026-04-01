from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
import subprocess
import psutil
import pandas as pd
import json
import os

load_dotenv()

VEL_API_KEY = os.getenv("VEL_API_KEY")
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
security = HTTPBearer()

def verify_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != VEL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

app = FastAPI(title="Velframe Web")

def get_service_status(service):
    result = subprocess.run(
        ["systemctl", "is-active", service],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def get_system_stats():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    cpu_freq = psutil.cpu_freq()
    return {
        "cpu_percent": cpu,
        "cpu_freq": round(cpu_freq.current),
        "cpu_cores": psutil.cpu_count(),
        "ram_used": ram.used // (1024**3),
        "ram_total": ram.total // (1024**3),
        "ram_percent": ram.percent,
        "disk_used": disk.used // (1024**3),
        "disk_total": disk.total // (1024**3),
        "disk_percent": disk.percent,
        "uptime": subprocess.run(["uptime", "-p"], capture_output=True, text=True).stdout.strip()
    }

def get_db_stats():
    try:
        df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
        engine_count = df["engine"].nunique()
        row_count = len(df)
    except:
        engine_count = 0
        row_count = 0

    try:
        mods_df = pd.read_csv(os.path.join(BASE_DIR, "mods_specs.csv"))
        mods_count = mods_df["mod"].nunique()
    except:
        mods_count = 0

    try:
        with open(os.path.join(BASE_DIR, "index_manifest.json")) as f:
            manifest = json.load(f)
        index_version = manifest.get("version", 0)
        last_built = manifest.get("last_built", "Never")
    except:
        index_version = 0
        last_built = "Never"

    try:
        with open(os.path.join(BASE_DIR, "scraper.log")) as f:
            lines = f.readlines()
        last_scrape = lines[-1].strip() if lines else "Never"
    except:
        last_scrape = "Never"

    return {
        "engines": engine_count,
        "mods": mods_count,
        "rows": row_count,
        "index_version": index_version,
        "last_built": last_built,
        "last_scrape": last_scrape
    }

@app.get("/api/status")
async def status():
    services = ["vel", "vel-watchdog", "ollama", "docker", "cockpit.socket", "tailscaled", "sshd"]
    return {
        "services": {s: get_service_status(s) for s in services},
        "system": get_system_stats(),
        "db": get_db_stats()
    }

@app.get("/api/logs/{service}")
async def logs(service: str):
    allowed = ["vel", "ollama", "vel-watchdog", "docker"]
    if service not in allowed:
        raise HTTPException(status_code=400, detail="Invalid service")
    result = subprocess.run(
        ["journalctl", "-u", service, "-n", "100", "--no-pager"],
        capture_output=True, text=True
    )
    return {"logs": result.stdout}

@app.post("/api/restart/{service}")
async def restart(service: str, key: str = Depends(verify_key)):
    allowed = ["vel", "ollama", "vel-watchdog", "docker"]
    if service not in allowed:
        raise HTTPException(status_code=400, detail="Invalid service")
    subprocess.run(["sudo", "systemctl", "restart", service])
    return {"status": "restarted", "service": service}

@app.post("/api/run/{script}")
async def run_script(script: str, key: str = Depends(verify_key)):
    allowed = ["scraper", "discovery", "cleaner", "ingest", "backup"]
    if script not in allowed:
        raise HTTPException(status_code=400, detail="Invalid script")
    result = subprocess.run(
        ["python3", os.path.join(BASE_DIR, f"{script}.py")],
        capture_output=True, text=True
    )
    return {"output": result.stdout, "errors": result.stderr}

@app.post("/api/faillock/reset")
async def reset_faillock(key: str = Depends(verify_key)):
    subprocess.run(["sudo", "faillock", "--user", "_homeos", "--reset"])
    return {"status": "reset"}

@app.get("/api/queries")
async def queries():
    try:
        with open(os.path.join(BASE_DIR, "query.log")) as f:
            lines = f.readlines()
        return {"total": len(lines), "recent": [l.strip() for l in lines[-50:]]}
    except:
        return {"total": 0, "recent": []}

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(BASE_DIR, "velframe_ui.html")) as f:
        return f.read()
