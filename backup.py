import os
import shutil
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/home/_homeos/vel-backups")
KEEP_DAYS = 7

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "backup.log"),
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def run_backup():
    print(f"Starting backup at {datetime.now()}")
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_name = f"vel-backup-{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    os.makedirs(backup_path, exist_ok=True)
    for f in ["engine_specs.csv", "engine_specs.xlsx", "scraper.py",
              "discovery.py", "cleaner.py", "rag.py", "server.py",
              "velframe.py", "velframe_web.py", "watchdog.py",
              "ingest.py", "mods_scraper.py", "index_manager.py", ".env"]:
        src = os.path.join(BASE_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, backup_path)

    shutil.make_archive(backup_path, 'zip', backup_path)
    shutil.rmtree(backup_path)
    print(f"Backup saved: {backup_path}.zip")
    logging.info(f"Backup saved: {backup_path}.zip")

    now = datetime.now().timestamp()
    for f in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, f)
        if os.path.isfile(fpath):
            age_days = (now - os.path.getmtime(fpath)) / 86400
            if age_days > KEEP_DAYS:
                os.remove(fpath)
                print(f"Deleted old backup: {f}")
                logging.info(f"Deleted old backup: {f}")

if __name__ == "__main__":
    run_backup()
