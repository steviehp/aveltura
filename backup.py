import os
import shutil
import logging
from datetime import datetime

logging.basicConfig(
    filename="/home/_homeos/engine-analysis/backup.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

BACKUP_DIR = "/home/_homeos/vel-backups"
SOURCE_DIR = "/home/_homeos/engine-analysis"
KEEP_DAYS = 7

def run_backup():
    print(f"Starting backup at {datetime.now()}")
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_name = f"vel-backup-{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    # Copy important files only, not storage index
    os.makedirs(backup_path, exist_ok=True)
    for f in ["engine_specs.csv", "engine_specs.xlsx", "scraper.py",
              "discovery.py", "cleaner.py", "rag.py", "server.py",
              "velframe.py", "watchdog.py", ".env"]:
        src = os.path.join(SOURCE_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, backup_path)

    # Compress it
    shutil.make_archive(backup_path, 'zip', backup_path)
    shutil.rmtree(backup_path)
    print(f"Backup saved: {backup_path}.zip")
    logging.info(f"Backup saved: {backup_path}.zip")

    # Delete backups older than 7 days
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
