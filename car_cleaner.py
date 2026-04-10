"""
car_cleaner.py — Phase 3: Vehicle Spec Cleaning + Smart Duplicate Merger

Reads raw_vehicle_specs.csv and:
1. Validates each row is actually a car with real specs
2. Marks missing specs as NULL (keeps row, flags for future scrape)
3. Detects duplicates — same vehicle/generation/trim
4. Smart merge — extracts best data from each duplicate
5. Confidence check — validates merged fields against EPA + plausibility
6. Outputs clean_vehicle_specs.csv

Confidence scoring (0-100):
  25pts — value in plausible range for displacement
  25pts — HP/torque ratio makes sense
  25pts — EPA displacement corroborates
  25pts — matches verified_seeds data
  Threshold: 70pts to accept merged field
"""

import os
import re
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "car_cleaner.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CONFIDENCE_THRESHOLD = 70   # minimum score to accept a merged field value

# ── Plausibility bounds ───────────────────────────────────────────────────────

BOUNDS = {
    "power_hp":        (30,    3000),
    "torque_nm":       (20,    5000),
    "displacement_cc": (50,   15000),
}

# HP/litre plausibility range
HP_PER_LITRE_MIN = 20    # very low (old NA diesel)
HP_PER_LITRE_MAX = 500   # extreme (Bugatti Chiron ~188hp/L, Koenigsegg ~300hp/L)

# Known bad values — these exact numbers appear as Wikipedia scraping artifacts
KNOWN_BAD_VALUES = {0, 1, 999, 9999, 10000, 99999}

# ── Non-car detection ─────────────────────────────────────────────────────────

NON_CAR_SIGNALS = [
    "formula 1", "f1", "formula one", "indycar", "nascar",
    "motorcycle", "motorbike", "scooter", "moped",
    "truck", "lorry", "semi", "tractor",
    "concept only", "show car", "prototype", "one-off",
    "racing only", "race car exclusive", "not road legal",
    "bus", "coach", "van", "minibus",
    "boat", "aircraft", "plane",
]

# Minimum data to keep a row
REQUIRED_FIELDS = ["vehicle", "manufacturer"]
USEFUL_FIELDS   = ["power_hp", "displacement_cc", "torque_nm", "engine"]


# ── EPA data loader ───────────────────────────────────────────────────────────

def load_epa_displacements():
    """Load unique displacement values from EPA cache for cross-validation."""
    epa_path = os.path.join(BASE_DIR, "epa_vehicles.csv")
    if not os.path.exists(epa_path):
        return set()
    try:
        df = pd.read_csv(epa_path, usecols=["displ"])
        # EPA stores in litres — convert to cc set rounded to nearest 100
        displ_set = set()
        for val in df["displ"].dropna():
            cc = round(float(val) * 1000 / 100) * 100
            displ_set.add(cc)
        return displ_set
    except Exception as e:
        logging.error(f"Could not load EPA data: {e}")
        return set()


def load_verified_seeds():
    """Load verified seeds for cross-validation."""
    seeds_path = os.path.join(BASE_DIR, "verified_seeds.csv")
    if not os.path.exists(seeds_path):
        return pd.DataFrame()
    try:
        return pd.read_csv(seeds_path)
    except Exception:
        return pd.DataFrame()


# ── Validation helpers ────────────────────────────────────────────────────────

def is_plausible(field, value):
    """Check if a numeric value is within plausible bounds for its field."""
    if value is None or pd.isna(value):
        return False
    try:
        v = float(value)
    except (ValueError, TypeError):
        return False
    if v in KNOWN_BAD_VALUES:
        return False
    lo, hi = BOUNDS.get(field, (0, float("inf")))
    return lo < v < hi


def hp_per_litre_ok(power_hp, displacement_cc):
    """Return True if HP/litre ratio is within plausible range."""
    try:
        if not power_hp or not displacement_cc:
            return True   # can't check, don't penalise
        ratio = float(power_hp) / (float(displacement_cc) / 1000)
        return HP_PER_LITRE_MIN <= ratio <= HP_PER_LITRE_MAX
    except Exception:
        return True


def epa_corroborates_displacement(displacement_cc, epa_set):
    """
    Return True if the displacement is close to any EPA-listed value.
    Tolerance: ±150cc (covers rounding differences e.g. 4951 vs 5000).
    """
    if not displacement_cc or not epa_set:
        return False
    try:
        val = float(displacement_cc)
        return any(abs(val - epa) <= 150 for epa in epa_set)
    except Exception:
        return False


def seeds_corroborate(engine_name, field, value, seeds_df):
    """Return True if verified seeds have a similar value for this engine."""
    if seeds_df.empty or not engine_name or not value:
        return False
    try:
        matches = seeds_df[seeds_df["engine"].str.contains(
            engine_name.split()[0], case=False, na=False
        )]
        if matches.empty or field not in matches.columns:
            return False
        seed_vals = matches[field].dropna()
        if seed_vals.empty:
            return False
        # Within 15% of any seed value
        val = float(value)
        return any(abs(val - float(sv)) / max(float(sv), 1) < 0.15
                   for sv in seed_vals)
    except Exception:
        return False


def confidence_score(field, value, power_hp=None, displacement_cc=None,
                     engine_name=None, epa_set=None, seeds_df=None):
    """
    Score a field value 0–100.
    Returns (score, breakdown_dict)
    """
    score = 0
    breakdown = {}

    # 25pts — plausibility bounds
    if is_plausible(field, value):
        score += 25
        breakdown["plausible_range"] = 25
    else:
        breakdown["plausible_range"] = 0

    # 25pts — HP/torque ratio
    if field == "torque_nm" and power_hp and displacement_cc:
        if hp_per_litre_ok(power_hp, displacement_cc):
            score += 25
            breakdown["hp_ratio"] = 25
        else:
            breakdown["hp_ratio"] = 0
    elif field == "displacement_cc" and power_hp:
        if hp_per_litre_ok(power_hp, value):
            score += 25
            breakdown["hp_ratio"] = 25
        else:
            breakdown["hp_ratio"] = 0
    elif field == "power_hp" and displacement_cc:
        if hp_per_litre_ok(value, displacement_cc):
            score += 25
            breakdown["hp_ratio"] = 25
        else:
            breakdown["hp_ratio"] = 0
    else:
        score += 12   # neutral — can't check
        breakdown["hp_ratio"] = 12

    # 25pts — EPA corroboration
    epa_field = field if field == "displacement_cc" else None
    if epa_field and epa_set:
        if epa_corroborates_displacement(value, epa_set):
            score += 25
            breakdown["epa_corroboration"] = 25
        else:
            breakdown["epa_corroboration"] = 0
    else:
        score += 12   # neutral
        breakdown["epa_corroboration"] = 12

    # 25pts — verified seeds
    if seeds_df is not None and not seeds_df.empty and engine_name:
        if seeds_corroborate(engine_name, field, value, seeds_df):
            score += 25
            breakdown["seeds_match"] = 25
        else:
            breakdown["seeds_match"] = 0
    else:
        score += 12   # neutral
        breakdown["seeds_match"] = 12

    return min(score, 100), breakdown


# ── Row validation ────────────────────────────────────────────────────────────

def is_car_row(row):
    """Return True if this row represents an actual car."""
    vehicle = str(row.get("vehicle", "")).lower()
    engine  = str(row.get("engine", "")).lower()

    for signal in NON_CAR_SIGNALS:
        if signal in vehicle or signal in engine:
            return False

    # Must have vehicle and manufacturer
    for field in REQUIRED_FIELDS:
        val = row.get(field, "")
        if not val or pd.isna(val) or str(val).strip() == "":
            return False

    return True


def validate_row(row):
    """
    Validate numeric fields — mark implausible values as NULL.
    Returns cleaned row.
    """
    row = dict(row)

    for field, (lo, hi) in BOUNDS.items():
        val = row.get(field)
        if val is None or pd.isna(val):
            continue
        try:
            v = float(val)
            if v in KNOWN_BAD_VALUES or not (lo < v < hi):
                logging.info(
                    f"Nulled {field}={v} for {row.get('vehicle')} "
                    f"(out of bounds {lo}-{hi})"
                )
                row[field] = None
        except (ValueError, TypeError):
            row[field] = None

    # Cross-validate HP/displacement
    hp   = row.get("power_hp")
    disp = row.get("displacement_cc")
    if hp and disp:
        try:
            if not hp_per_litre_ok(float(hp), float(disp)):
                logging.info(
                    f"Cross-validate failed for {row.get('vehicle')}: "
                    f"{hp}hp / {disp}cc = {float(hp)/(float(disp)/1000):.1f} hp/L"
                )
                # Null the less reliable one — power is often wrong, disp usually right
                row["power_hp"] = None
        except Exception:
            pass

    return row


def count_useful_fields(row):
    """Count how many useful fields have non-null values."""
    count = 0
    for field in USEFUL_FIELDS:
        val = row.get(field)
        if val is not None and not pd.isna(val) and str(val).strip() != "":
            count += 1
    return count


# ── Duplicate detection + merge ───────────────────────────────────────────────

def dedup_key(row):
    """Generate deduplication key for a row."""
    vehicle = str(row.get("vehicle", "")).lower().strip()
    gen     = str(row.get("generation", "")).lower().strip()
    trim    = str(row.get("trim", "")).lower().strip()
    # Normalize generation labels
    gen = re.sub(r'\s+', ' ', gen)
    return f"{vehicle}|{gen}|{trim}"


def smart_merge(rows, epa_set, seeds_df):
    """
    Merge a list of duplicate rows into one best row.

    For each field:
    1. Collect all non-null values
    2. If only one unique value — use it
    3. If multiple — run confidence check on each
    4. Use value with highest confidence score if >= threshold
    5. If no value passes threshold — mark as NULL
    """
    if len(rows) == 1:
        return rows[0]

    merged = dict(rows[0])  # start with first row as base
    engine_name = str(merged.get("engine", ""))

    # Fields to attempt merging
    merge_fields = ["power_hp", "torque_nm", "displacement_cc", "engine",
                    "year_start", "year_end", "layout", "body_style"]

    for field in merge_fields:
        # Collect all non-null values from all duplicates
        values = []
        for row in rows:
            val = row.get(field)
            if val is not None and not pd.isna(val) and str(val).strip() != "":
                values.append(val)

        if not values:
            merged[field] = None
            continue

        unique_vals = list(dict.fromkeys(values))  # preserves order, deduped

        if len(unique_vals) == 1:
            merged[field] = unique_vals[0]
            continue

        # Multiple values — run confidence check
        if field in BOUNDS:
            best_val   = None
            best_score = -1

            for val in unique_vals:
                score, breakdown = confidence_score(
                    field, val,
                    power_hp       = merged.get("power_hp"),
                    displacement_cc= merged.get("displacement_cc"),
                    engine_name    = engine_name,
                    epa_set        = epa_set,
                    seeds_df       = seeds_df,
                )
                logging.info(
                    f"Confidence {field}={val} for {merged.get('vehicle')}: "
                    f"{score}% {breakdown}"
                )
                if score > best_score:
                    best_score = score
                    best_val   = val

            if best_score >= CONFIDENCE_THRESHOLD:
                merged[field] = best_val
                merged[f"{field}_confidence"] = best_score
            else:
                merged[field] = None
                logging.info(
                    f"No value passed confidence threshold for {field} "
                    f"in {merged.get('vehicle')} (best: {best_score}%)"
                )
        else:
            # Non-numeric — take the longest/most detailed value
            merged[field] = max(unique_vals, key=lambda x: len(str(x)))

    # Track that this was a merge
    merged["merged_from"] = len(rows)
    return merged


# ── Runner ────────────────────────────────────────────────────────────────────

def run_car_cleaner():
    print(f"Starting car cleaner at {datetime.now()}")
    logging.info("Car cleaner started")

    input_path  = os.path.join(BASE_DIR, "raw_vehicle_specs.csv")
    output_path = os.path.join(BASE_DIR, "clean_vehicle_specs.csv")

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found — run generation_scraper.py first")
        return pd.DataFrame()

    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} raw rows")

    # Load reference data for confidence scoring
    print("Loading EPA and seeds data for confidence scoring...")
    epa_set   = load_epa_displacements()
    seeds_df  = load_verified_seeds()
    print(f"  EPA displacements: {len(epa_set)} values")
    print(f"  Verified seeds: {len(seeds_df)} engines")

    # ── Phase 1: Filter non-cars ──────────────────────────────────────────────
    print("\nPhase 1: Filtering non-car rows...")
    original_count = len(df)
    df = df[df.apply(is_car_row, axis=1)]
    print(f"  Removed {original_count - len(df)} non-car rows")
    print(f"  Remaining: {len(df)} rows")

    # ── Phase 2: Validate numeric fields ─────────────────────────────────────
    print("\nPhase 2: Validating numeric fields...")
    df = pd.DataFrame([validate_row(row) for _, row in df.iterrows()])

    # Mark rows with missing specs
    df["missing_specs"] = df.apply(
        lambda r: [f for f in USEFUL_FIELDS
                   if r.get(f) is None or pd.isna(r.get(f))
                   or str(r.get(f)).strip() == ""],
        axis=1
    ).apply(lambda x: ",".join(x) if x else "")

    incomplete = (df["missing_specs"] != "").sum()
    print(f"  {incomplete} rows have missing specs (marked NULL, kept)")

    # ── Phase 3: Duplicate detection + merge ─────────────────────────────────
    print("\nPhase 3: Duplicate detection and smart merge...")

    df["_dedup_key"] = df.apply(dedup_key, axis=1)
    groups = df.groupby("_dedup_key")
    dup_groups = {k: v for k, v in groups if len(v) > 1}

    print(f"  Found {len(dup_groups)} duplicate groups")

    merged_rows = []
    single_rows = []

    for key, group in groups:
        rows = group.to_dict("records")
        if len(rows) == 1:
            single_rows.append(rows[0])
        else:
            print(f"  Merging: {key} ({len(rows)} entries)")
            merged = smart_merge(rows, epa_set, seeds_df)
            merged_rows.append(merged)

    all_rows = single_rows + merged_rows
    print(f"  {len(single_rows)} unique rows + {len(merged_rows)} merged rows")
    print(f"  Total after dedup: {len(all_rows)} rows")

    # ── Phase 4: Final cleanup ────────────────────────────────────────────────
    print("\nPhase 4: Final cleanup...")
    clean_df = pd.DataFrame(all_rows)

    # Drop internal columns
    clean_df = clean_df.drop(columns=["_dedup_key"], errors="ignore")

    # Ensure numeric types
    for field in ["power_hp", "torque_nm", "displacement_cc", "year_start", "year_end"]:
        if field in clean_df.columns:
            clean_df[field] = pd.to_numeric(clean_df[field], errors="coerce")

    # Sort by manufacturer, vehicle, generation
    sort_cols = [c for c in ["manufacturer", "vehicle", "generation", "trim"]
                 if c in clean_df.columns]
    if sort_cols:
        clean_df = clean_df.sort_values(sort_cols).reset_index(drop=True)

    # ── Save ──────────────────────────────────────────────────────────────────
    clean_df.to_csv(output_path, index=False)
    print(f"\nSaved {len(clean_df)} clean rows → {output_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Clean rows:          {len(clean_df)}")
    if "manufacturer" in clean_df.columns:
        print(f"Manufacturers:       {clean_df['manufacturer'].nunique()}")
    if "vehicle" in clean_df.columns:
        print(f"Unique vehicles:     {clean_df['vehicle'].nunique()}")
    if "power_hp" in clean_df.columns:
        filled = clean_df["power_hp"].notna().sum()
        print(f"Rows with power_hp:  {filled} ({100*filled//len(clean_df)}%)")
    if "displacement_cc" in clean_df.columns:
        filled = clean_df["displacement_cc"].notna().sum()
        print(f"Rows with disp:      {filled} ({100*filled//len(clean_df)}%)")
    if "missing_specs" in clean_df.columns:
        incomplete = (clean_df["missing_specs"] != "").sum()
        print(f"Incomplete rows:     {incomplete} (flagged, kept)")
    if "merged_from" in clean_df.columns:
        merged = clean_df["merged_from"].notna().sum()
        print(f"Merged duplicates:   {merged}")

    logging.info(
        f"Car cleaner complete: {len(clean_df)} clean rows, "
        f"{len(dup_groups)} duplicate groups merged"
    )
    return clean_df


if __name__ == "__main__":
    run_car_cleaner()
