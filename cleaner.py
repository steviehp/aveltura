import pandas as pd
import re
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "cleaner.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Engine names that are clearly not real engine names
INVALID_ENGINE_NAMES = {
    "turbo", "turbocharged", "twin-turbo", "twin-turbocharged",
    "quad-turbocharged", "quad turbo", "supercharged",
    "naturally aspirated", "petrol", "diesel", "gasoline",
    "electric", "hybrid", "sequential", "manual", "automatic",
    "inline", "boxer", "flat", "rotary", "v6", "v8", "v10", "v12",
    "awd", "rwd", "fwd", "4wd", "all-wheel", "rear-wheel",
    "twin turbo", "single turbo", "bi-turbo", "tri-turbo",
}

# Spec keys that legitimately hold pure-numeric values —
# don't flag these as garbage even if value is just digits
NUMERIC_SPEC_KEYS = {
    "redline", "rpm", "production", "year", "bore", "stroke",
    "compression", "displacement", "power", "torque", "hp", "bhp",
    "kw", "output", "capacity", "cc", "horsepower",
}


# ── Value cleaning ────────────────────────────────────────────────────────────

def normalize_units(val):
    """Normalize unit spellings BEFORE stripping non-ASCII so we don't lose
    symbols like · or ³ before we've had a chance to replace them."""
    if not isinstance(val, str):
        return val
    replacements = [
        ("horsepower",       "hp"),
        ("Horsepower",       "hp"),
        ("kilowatts",        "kW"),
        ("Newton metres",    "Nm"),
        ("newton metres",    "Nm"),
        ("N·m",              "Nm"),
        ("n·m",              "Nm"),
        ("pound-feet",       "lb-ft"),
        ("pound feet",       "lb-ft"),
        ("cubic centimetres","cc"),
        ("cubic centimeters","cc"),
        ("cm³",              "cc"),
        ("cm3",              "cc"),
        ("cubic inches",     "cu in"),
        ("cu. in.",          "cu in"),
    ]
    for old, new in replacements:
        val = val.replace(old, new)
    return val


def clean_value(val):
    if not isinstance(val, str):
        return val
    # Strip wiki citation brackets e.g. [1], [note 2]
    val = re.sub(r'\[.*?\]', '', val)
    # Collapse whitespace
    val = re.sub(r'\s+', ' ', val).strip()
    # Strip non-ASCII AFTER unit normalization has already run
    val = val.encode('ascii', 'ignore').decode('ascii')
    return val


# ── Row / name filters ────────────────────────────────────────────────────────

def spec_is_numeric_type(spec_str):
    """Return True if the spec key suggests a purely numeric value is valid."""
    spec_lower = spec_str.lower()
    return any(key in spec_lower for key in NUMERIC_SPEC_KEYS)


def is_garbage_row(row):
    spec  = str(row["spec"]).strip()
    value = str(row["value"]).strip()

    # Too short to be meaningful
    if len(spec) < 2 or len(value) < 1:
        return True

    # Pure-digit value: only garbage if the spec key doesn't expect numbers.
    # e.g. value="8500" for spec="Redline" is fine;
    #      value="1234" for spec="Also called" is garbage.
    if re.match(r'^\d+$', value):
        if not spec_is_numeric_type(spec):
            return True

    # Reference / citation artifacts
    REF_SIGNALS = ["retrieved", "archived", "cite", "isbn", "doi",
                   "wikimedia", "wikipedia", "commons.wiki"]
    spec_lower  = spec.lower()
    value_lower = value.lower()
    if any(s in spec_lower  for s in REF_SIGNALS):
        return True
    if any(s in value_lower for s in REF_SIGNALS):
        return True

    # Absurdly large power value (scraper noise, not a real engine)
    if "power" in spec_lower or "hp" in spec_lower or "bhp" in spec_lower:
        numbers = re.findall(r'\d+', value)
        if numbers and int(numbers[0]) > 10000:
            return True

    return False


def is_invalid_engine_name(engine_name):
    """
    Return True when the engine name is a generic descriptor with no
    specific identifier (no manufacturer prefix, no code, etc.).

    FIX: removed the redundant for-loop that duplicated the set lookup.
    """
    name = str(engine_name).lower().strip()

    # Set lookup covers exact matches — no for-loop needed
    if name in INVALID_ENGINE_NAMES:
        return True

    # Too short to be a real engine name
    if len(name) < 3:
        return True

    return False


# ── Main runner ───────────────────────────────────────────────────────────────

def run_cleaner():
    print(f"Starting cleaner at {datetime.now()}")
    logging.info("Cleaner started")

    csv_path = os.path.join(BASE_DIR, "engine_specs.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found — run scraper.py first")
        logging.error("engine_specs.csv not found — cleaner aborted")
        return

    df = pd.read_csv(csv_path)
    original_rows = len(df)
    print(f"Loaded {original_rows} rows")

    # ── 1. Remove invalid engine names ───────────────────────────────────────
    if "engine" in df.columns:
        invalid_mask    = df["engine"].apply(is_invalid_engine_name)
        invalid_engines = df[invalid_mask]["engine"].unique()
        if len(invalid_engines):
            print(f"  Removing {len(invalid_engines)} invalid engine name(s): "
                  f"{list(invalid_engines)}")
            logging.info(f"Invalid engine names removed: {list(invalid_engines)}")
        df = df[~invalid_mask]

    # ── 2. Normalize units BEFORE stripping non-ASCII ─────────────────────────
    df["value"] = df["value"].apply(normalize_units)

    # ── 3. Clean text (strip brackets, collapse whitespace, drop non-ASCII) ───
    df["spec"]  = df["spec"].apply(clean_value)
    df["value"] = df["value"].apply(clean_value)

    # ── 4. Remove garbage rows ────────────────────────────────────────────────
    garbage_mask = df.apply(is_garbage_row, axis=1)
    print(f"  Garbage rows: {garbage_mask.sum()}")
    df = df[~garbage_mask]

    # ── 5. Remove duplicates ──────────────────────────────────────────────────
    dedup_cols = (["engine", "variant", "spec"] if "variant" in df.columns
                  else ["engine", "spec"])
    before_dedup = len(df)
    df = df.drop_duplicates(subset=dedup_cols, keep="first")
    print(f"  Duplicates removed: {before_dedup - len(df)}")

    # ── 6. Drop rows that are empty after cleaning ────────────────────────────
    df = df[df["spec"].str.strip()  != ""]
    df = df[df["value"].str.strip() != ""]

    # ── 7. Report most common spec keys (helps tune SPEC_MAPPING) ────────────
    print("\nTop 20 spec keys in cleaned data:")
    print(df["spec"].value_counts().head(20).to_string())

    # ── 8. Save ───────────────────────────────────────────────────────────────
    cleaned_rows = len(df)
    removed      = original_rows - cleaned_rows
    df.to_csv(csv_path, index=False)
    df.to_excel(os.path.join(BASE_DIR, "engine_specs.xlsx"), index=False)

    print(f"\nDone — {cleaned_rows} rows kept, {removed} removed")
    logging.info(f"Cleaner complete: {cleaned_rows} rows kept, {removed} removed")


if __name__ == "__main__":
    run_cleaner()
