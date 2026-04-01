import json
import os
import shutil
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MANIFEST_FILE = "index_manifest.json"
STORAGE_V1 = "storage_v1"
STORAGE_V2 = "storage_v2"
STORAGE_CURRENT = "storage"

def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return {"engines": {}, "mods": {}, "last_built": None, "version": 0}

def save_manifest(manifest):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

def get_new_entries(manifest):
    new_engines = []
    new_mods = []

    # Check engines
    if os.path.exists("engine_specs.csv"):
        df = pd.read_csv("engine_specs.csv")
        for engine_name in df["engine"].unique():
            if engine_name not in manifest["engines"]:
                new_engines.append(engine_name)

    # Check mods
    if os.path.exists("mods_specs.csv"):
        mods_df = pd.read_csv("mods_specs.csv")
        for mod_name in mods_df["mod"].unique():
            if mod_name not in manifest["mods"]:
                new_mods.append(mod_name)

    return new_engines, new_mods

def rotate_storage():
    # Delete oldest version
    if os.path.exists(STORAGE_V1):
        shutil.rmtree(STORAGE_V1)
        print("Deleted old storage_v1")

    # Move v2 to v1
    if os.path.exists(STORAGE_V2):
        shutil.copytree(STORAGE_V2, STORAGE_V1)
        shutil.rmtree(STORAGE_V2)
        print("Rotated storage_v2 to storage_v1")

    # Move current to v2
    if os.path.exists(STORAGE_CURRENT):
        shutil.copytree(STORAGE_CURRENT, STORAGE_V2)
        print("Saved current storage as storage_v2")

def rollback():
    if os.path.exists(STORAGE_V1):
        if os.path.exists(STORAGE_CURRENT):
            shutil.rmtree(STORAGE_CURRENT)
        shutil.copytree(STORAGE_V1, STORAGE_CURRENT)
        print("Rolled back to storage_v1")
        return True
    print("No backup available to rollback to")
    return False

def update_manifest(new_engines, new_mods):
    manifest = load_manifest()
    timestamp = datetime.now().isoformat()
    for engine in new_engines:
        manifest["engines"][engine] = timestamp
    for mod in new_mods:
        manifest["mods"][mod] = timestamp
    manifest["last_built"] = timestamp
    manifest["version"] += 1
    save_manifest(manifest)
    print(f"Manifest updated to version {manifest['version']}")

if __name__ == "__main__":
    manifest = load_manifest()
    new_engines, new_mods = get_new_entries(manifest)
    print(f"New engines: {len(new_engines)}")
    print(f"New mods: {len(new_mods)}")
