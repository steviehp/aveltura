"""
normalizer.py — Phase 4: Normalization Pipeline

Two data streams:
  Stream A: clean_vehicle_specs.csv (vehicle-first, from generation_scraper)
            → unit conversion → engine_applications.csv

  Stream B: engine_specs.csv (engine-first, from scraper.py)
            → unit conversion, confidence scoring → engine_normalized.csv

Both streams feed into the RAG pipeline.
verified_seeds.csv overrides everything in both streams.
"""

import pandas as pd
import re
import os
import logging
from dotenv import load_dotenv
from engine_code_parser import parse_displacement_from_code

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "normalizer.log"),
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

SPEC_MAPPING = {
    "displacement": ["displacement", "engine displacement", "cubic capacity",
                     "swept volume", "capacity"],
    "bore_mm":      ["bore", "cylinder bore", "bore diameter", "bore size"],
    "stroke_mm":    ["stroke", "piston stroke", "stroke length"],
    "compression_ratio": ["compression ratio", "compression", "comp ratio"],
    "power_hp":     ["power", "power output", "horsepower", "max power",
                     "maximum power", "bhp", "hp", "output"],
    "torque_nm":    ["torque", "max torque", "maximum torque", "torque output"],
    "redline_rpm":  ["redline", "red line", "rev limit", "maximum rpm",
                     "max rpm", "max. engine speed"],
    "configuration":["configuration", "engine type", "layout",
                     "cylinder arrangement", "type"],
    "block_material":["cylinder block material", "block material",
                      "cylinder block", "block"],
    "head_material":["cylinder head material", "head material", "cylinder head"],
    "valvetrain":   ["valvetrain", "valve train", "valves", "valve configuration",
                     "valve mechanism", "valve diameters", "camshaft"],
    "fuel_system":  ["fuel system", "fuel delivery", "fuelsystem", "fuel type",
                     "fuel injection"],
    "cooling":      ["cooling", "cooling system"],
    "manufacturer": ["manufacturer", "made by", "produced by", "builder"],
    "production":   ["production", "production years", "years produced",
                     "built", "first year"],
    "successor":    ["successor", "replaced by"],
    "predecessor":  ["predecessor", "replaced"],
    "forced_induction": ["supercharger", "turbocharger", "forced induction",
                         "boost pressure", "turbo", "compressor"],
    "transmission": ["transmission", "gearbox", "gear"],
    "engine_code":  ["engine code", "engine codes", "also called",
                     "variant", "version"],
    "designer":     ["designer", "designed by"],
    "weight_kg":    ["dry weight", "curb weight", "weight"],
    "generation":   ["generation"],
    "oil_system":   ["oil system", "lubrication", "oil pump"],
    "dimensions":   ["dimensions", "wheelbase", "width", "height", "length"],
    "aspiration":   ["aspiration", "naturally aspirated", "turbocharged",
                     "supercharged"],
    "rod_length_mm":["con rod length", "rod length", "connecting rod"],
    "bore_spacing_mm":["spacing", "bore spacing"],
}

NUMERIC_COLS = ["displacement", "power_hp", "torque_nm", "bore_mm",
                "stroke_mm", "compression_ratio", "redline_rpm"]
TEXT_COLS    = ["block_material", "head_material", "configuration"]


def extract_first_number(val):
    val = str(val).replace(",", "")
    range_match = re.findall(r'(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', val)
    if range_match:
        low, high = float(range_match[0][0]), float(range_match[0][1])
        return (low + high) / 2
    nums = re.findall(r'\d+\.?\d*', val)
    return float(nums[0]) if nums else None


def convert_power_to_hp(value_str):
    if pd.isna(value_str):
        return None
    val = str(value_str).lower().replace(",", "")
    number = extract_first_number(val)
    if number is None:
        return None
    if "kw" in val:
        converted = round(number * 1.341, 1)
    elif "ps" in val or "cv" in val or "ch" in val:
        converted = round(number * 0.9863, 1)
    else:
        converted = round(number, 1)
    return converted if 30 < converted < 3000 else None


def convert_torque_to_nm(value_str):
    if pd.isna(value_str):
        return None
    val = str(value_str).lower().replace(",", "")
    number = extract_first_number(val)
    if number is None:
        return None
    if "lb" in val and "ft" in val:
        converted = round(number * 1.356, 1)
    elif "kgm" in val or "kgf" in val:
        converted = round(number * 9.807, 1)
    else:
        converted = round(number, 1)
    return converted if 10 < converted < 5000 else None


def convert_displacement_to_cc(value_str):
    if pd.isna(value_str):
        return None
    val = str(value_str).lower().replace(",", "")
    cc_in_parens = re.findall(r'\((\d+)\s*cc\)', val)
    if cc_in_parens:
        number = float(cc_in_parens[0])
        return round(number, 1) if 50 < number < 100000 else None
    number = extract_first_number(val)
    if number is None:
        return None
    if "cu in" in val or "cuin" in val:
        converted = round(number * 16.387, 1)
    elif "l)" in val or " l" in val or "litre" in val or "liter" in val:
        converted = round(number * 1000, 1)
    elif "cc" in val or "cm³" in val or "cm3" in val:
        return round(number, 1) if 50 < number < 100000 else None
    else:
        if number < 30:
            converted = round(number * 1000, 1)
        elif number > 50:
            return round(number, 1) if number < 100000 else None
        else:
            converted = round(number * 1000, 1)
    return converted if 50 < converted < 100000 else None


def convert_bore_stroke_to_mm(value_str):
    if pd.isna(value_str):
        return None
    val = str(value_str).lower().replace(",", "")
    number = extract_first_number(val)
    if number is None:
        return None
    if "in" in val:
        converted = round(number * 25.4, 1)
        return converted if converted < 500 else None
    return round(number, 1) if number < 500 else None


def normalize_spec_name(spec):
    spec_lower = spec.lower().strip()
    for standard_name, variations in SPEC_MAPPING.items():
        for variation in variations:
            if variation in spec_lower or spec_lower in variation:
                return standard_name
    return None


def convert_value(standard_name, value_str):
    if standard_name == "power_hp":
        return convert_power_to_hp(value_str)
    elif standard_name == "torque_nm":
        return convert_torque_to_nm(value_str)
    elif standard_name == "displacement":
        return convert_displacement_to_cc(value_str)
    elif standard_name in ["bore_mm", "stroke_mm"]:
        return convert_bore_stroke_to_mm(value_str)
    return value_str


def detect_shared_bad_values(df, id_col="engine"):
    for spec in ["power_hp", "torque_nm", "displacement"]:
        if spec not in df.columns:
            continue
        for name, group in df.groupby(id_col):
            if len(group) < 2:
                continue
            all_values = group[spec].dropna()
            if len(all_values) >= 2 and all_values.nunique() == 1:
                df.loc[group.index, spec] = None
                logging.info(
                    f"Nulled shared {spec} {all_values.iloc[0]} "
                    f"for {name} (all identical)"
                )
    return df


def cross_validate_specs(df):
    if "displacement" not in df.columns or "power_hp" not in df.columns:
        return df
    for idx, row in df.iterrows():
        disp = row.get("displacement")
        hp   = row.get("power_hp")
        if pd.isna(disp) or pd.isna(hp):
            continue
        try:
            ratio = float(hp) / float(disp)
        except Exception:
            continue
        if ratio > 0.5:
            logging.info(
                f"Cross-validate: nulled displacement {disp}cc for "
                f"'{row.get('engine_variant', row.get('vehicle', ''))}' "
                f"(ratio {round(ratio,3)} HP/cc)"
            )
            df.at[idx, "displacement"] = None
        elif ratio < 0.02:
            logging.info(
                f"Cross-validate: nulled power_hp {hp} for "
                f"'{row.get('engine_variant', row.get('vehicle', ''))}' "
                f"(ratio {round(ratio,3)} HP/cc)"
            )
            df.at[idx, "power_hp"] = None
    return df


def load_verified_seeds():
    seeds_path = os.path.join(BASE_DIR, "verified_seeds.csv")
    if not os.path.exists(seeds_path):
        print("  No verified_seeds.csv found")
        return pd.DataFrame()
    df = pd.read_csv(seeds_path)
    df["engine_variant"] = df.apply(
        lambda r: f"{r['engine']} ({r['variant']})"
        if r["variant"] != "base" else r["engine"],
        axis=1
    )
    print(f"  Loaded {len(df)} verified seeds")
    return df


def merge_with_seeds(normalized_df, seeds_df):
    if seeds_df.empty:
        return normalized_df
    for col in NUMERIC_COLS:
        if col in normalized_df.columns:
            normalized_df[col] = pd.to_numeric(
                normalized_df[col], errors="coerce"
            )
    for _, seed_row in seeds_df.iterrows():
        engine  = seed_row["engine"]
        variant = seed_row["variant"]
        mask = (
            (normalized_df["engine"] == engine) &
            (normalized_df["variant"] == variant)
        )
        if mask.any():
            for col in NUMERIC_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    normalized_df.loc[mask, col] = float(seed_row[col])
            for col in TEXT_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    normalized_df.loc[mask, col] = str(seed_row[col])
            normalized_df.loc[mask, "confidence"] = "verified_manual"
        else:
            ev = (f"{engine} ({variant})" if variant != "base" else engine)
            new_row = {
                "engine":         engine,
                "variant":        variant,
                "engine_variant": ev,
                "confidence":     "verified_manual",
            }
            for col in NUMERIC_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    new_row[col] = float(seed_row[col])
            for col in TEXT_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    new_row[col] = str(seed_row[col])
            normalized_df = pd.concat(
                [normalized_df, pd.DataFrame([new_row])],
                ignore_index=True
            )
    return normalized_df


def mark_epa_verified(normalized_df):
    epa_path = os.path.join(BASE_DIR, "epa_vehicles.csv")
    if not os.path.exists(epa_path):
        print("  epa_vehicles.csv not found — skipping EPA verification")
        return normalized_df
    try:
        epa_df = pd.read_csv(epa_path)
    except Exception as e:
        print(f"  Could not read epa_vehicles.csv: {e}")
        return normalized_df
    if "displ" not in epa_df.columns:
        return normalized_df
    epa_displs = set(epa_df["displ"].dropna().unique())
    count = 0
    for idx, row in normalized_df.iterrows():
        if normalized_df.at[idx, "confidence"] == "verified_manual":
            continue
        disp_cc = row.get("displacement")
        if pd.isna(disp_cc):
            continue
        disp_l = round(float(disp_cc) / 1000, 1)
        if disp_l in epa_displs:
            normalized_df.at[idx, "confidence"] = "epa_verified"
            count += 1
    print(f"  EPA verified: {count} engine variants")
    return normalized_df


def normalize_vehicle_stream():
    """Stream A: clean_vehicle_specs → engine_applications.csv"""
    input_path  = os.path.join(BASE_DIR, "clean_vehicle_specs.csv")
    output_path = os.path.join(BASE_DIR, "engine_applications.csv")

    if not os.path.exists(input_path):
        print("  clean_vehicle_specs.csv not found — skipping vehicle stream")
        # Fall back to existing engine_applications.csv if present
        if os.path.exists(output_path):
            return pd.read_csv(output_path)
        return pd.DataFrame()

    df = pd.read_csv(input_path)
    print(f"  Loaded {len(df)} clean vehicle rows")

    if "power_hp" in df.columns:
        df["power_hp"] = df["power_hp"].apply(
            lambda v: convert_power_to_hp(str(v)) if pd.notna(v) else None
        )
    if "torque_nm" in df.columns:
        df["torque_nm"] = df["torque_nm"].apply(
            lambda v: convert_torque_to_nm(str(v)) if pd.notna(v) else None
        )
    if "displacement_cc" in df.columns:
        df["displacement_cc"] = df["displacement_cc"].apply(
            lambda v: convert_displacement_to_cc(str(v)) if pd.notna(v) else None
        )
        df = df.rename(columns={"displacement_cc": "displacement"})

    for field, lo, hi in [
        ("power_hp",     30,   3000),
        ("displacement", 50, 100000),
        ("torque_nm",    10,   5000),
    ]:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors="coerce")
            df.loc[~df[field].between(lo, hi, inclusive="neither"), field] = None

    if "confidence" not in df.columns:
        df["confidence"] = "wikipedia_scraped"

    # Preserve verified_manual rows from existing file
    existing_path = output_path
    if os.path.exists(existing_path):
        existing = pd.read_csv(existing_path)
        if "confidence" in existing.columns:
            verified = existing[existing["confidence"] == "verified_manual"]
        else:
            verified = existing[existing.get("source", pd.Series()).str.contains(
                "verified", na=False
            )] if "source" in existing.columns else pd.DataFrame()
        combined = pd.concat([verified, df], ignore_index=True)
        dedup_cols = [c for c in ["vehicle", "engine", "generation", "trim"]
                      if c in combined.columns]
        if dedup_cols:
            combined = combined.drop_duplicates(subset=dedup_cols, keep="first")
    else:
        combined = df

    combined.to_csv(output_path, index=False)
    print(f"  Saved {len(combined)} rows → engine_applications.csv")
    return combined


def normalize_engine_stream():
    """Stream B: engine_specs.csv → engine_normalized.csv"""
    csv_path = os.path.join(BASE_DIR, "engine_specs.csv")
    if not os.path.exists(csv_path):
        print("  engine_specs.csv not found — skipping engine stream")
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    print(f"  Loaded {len(df)} raw engine spec rows")

    has_variants = "variant" in df.columns
    group_cols   = ["engine", "variant"] if has_variants else ["engine"]

    normalized_rows = []
    unmapped = set()

    for keys, group in df.groupby(group_cols):
        if has_variants:
            engine_name, variant_name = keys
        else:
            engine_name  = keys
            variant_name = "base"

        ev_label = (
            f"{engine_name} ({variant_name})"
            if variant_name != "base" else engine_name
        )
        row = {
            "engine":         engine_name,
            "variant":        variant_name,
            "engine_variant": ev_label,
            "confidence":     "wikipedia_single",
        }

        hp_in_variant    = re.findall(r'(\d+)\s*hp', variant_name, re.IGNORECASE)
        liter_in_variant = re.findall(r'(\d+\.?\d*)L$', variant_name)
        if hp_in_variant:
            val = float(hp_in_variant[0])
            if 30 < val < 3000:
                row["power_hp"] = val
        if liter_in_variant:
            row["displacement"] = round(float(liter_in_variant[0]) * 1000, 1)

        for _, spec_row in group.iterrows():
            standard = normalize_spec_name(str(spec_row["spec"]))
            if standard:
                if standard not in row:
                    converted = convert_value(standard, spec_row["value"])
                    row[standard] = converted
            else:
                unmapped.add(str(spec_row["spec"]))

        code_cc = parse_displacement_from_code(engine_name)
        if code_cc:
            current_disp = row.get("displacement")
            if current_disp is None or pd.isna(current_disp):
                row["displacement"] = code_cc
            elif abs(float(current_disp) - code_cc) > 500:
                row["displacement"] = code_cc

        hint_rows = group[group["spec"] == "displacement_hint"]
        if not hint_rows.empty:
            hint_val = hint_rows.iloc[0]["value"]
            hint_num = extract_first_number(str(hint_val))
            if hint_num and hint_num < 30:
                hint_cc = round(hint_num * 1000, 1)
                current_disp = row.get("displacement")
                if current_disp is None or pd.isna(current_disp):
                    row["displacement"] = hint_cc

        for field, lo, hi in [
            ("power_hp",    30,   3000),
            ("displacement", 50, 100000),
            ("torque_nm",    10,   5000),
        ]:
            if field in row and row[field] is not None:
                try:
                    if not (lo < float(row[field]) < hi):
                        row[field] = None
                except Exception:
                    row[field] = None

        normalized_rows.append(row)

    normalized_df = pd.DataFrame(normalized_rows)

    for col in NUMERIC_COLS:
        if col in normalized_df.columns:
            normalized_df[col] = pd.to_numeric(
                normalized_df[col], errors="coerce"
            )

    print("  Detecting shared bad values...")
    normalized_df = detect_shared_bad_values(normalized_df, id_col="engine")
    print("  Cross validating specs...")
    normalized_df = cross_validate_specs(normalized_df)
    print("  Merging verified seeds...")
    seeds_df = load_verified_seeds()
    normalized_df = merge_with_seeds(normalized_df, seeds_df)
    print("  Marking EPA verified...")
    normalized_df = mark_epa_verified(normalized_df)

    confidence_order = {
        "verified_manual":  0,
        "epa_verified":     1,
        "wikipedia_single": 2,
    }
    normalized_df["confidence_rank"] = (
        normalized_df["confidence"].map(confidence_order).fillna(3)
    )
    normalized_df = normalized_df.sort_values("confidence_rank")
    normalized_df = normalized_df.drop_duplicates(
        subset=["engine", "variant"], keep="first"
    )
    normalized_df = normalized_df.drop(columns=["confidence_rank"])

    output_path = os.path.join(BASE_DIR, "engine_normalized.csv")
    normalized_df.to_csv(output_path, index=False)
    print(f"  Saved {len(normalized_df)} rows → engine_normalized.csv")

    if unmapped:
        with open(os.path.join(BASE_DIR, "unmapped_specs.txt"), "w") as f:
            for k in sorted(unmapped):
                f.write(k + "\n")

    if "confidence" in normalized_df.columns:
        print("\n  Confidence breakdown:")
        print(normalized_df["confidence"].value_counts().to_string())

    logging.info(f"Engine stream complete: {len(normalized_df)} variants")
    return normalized_df


def run_normalizer():
    print(f"Starting normalization at {datetime.now()}")
    logging.info("Normalization started")

    print("\n[Stream A] Vehicle-first normalization...")
    apps_df = normalize_vehicle_stream()

    print("\n[Stream B] Engine-first normalization...")
    engine_df = normalize_engine_stream()

    print(f"\nNormalization complete")
    print(f"  engine_applications.csv: {len(apps_df)} rows")
    print(f"  engine_normalized.csv:   {len(engine_df)} rows")

    logging.info(
        f"Normalization complete: "
        f"{len(apps_df)} application rows, "
        f"{len(engine_df)} engine variants"
    )
    return apps_df, engine_df


if __name__ == "__main__":
    from datetime import datetime
    apps_df, engine_df = run_normalizer()

    print("\nEngines with both displacement AND power_hp:")
    if "power_hp" in engine_df.columns and "displacement" in engine_df.columns:
        both = engine_df[
            ["engine_variant", "displacement", "power_hp", "confidence"]
        ].dropna(subset=["displacement", "power_hp"])
        print(f"Count: {len(both)}")
        print(both.to_string())
