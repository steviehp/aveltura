import pandas as pd
import re
import os
import logging
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "normalizer.log"),
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

SPEC_MAPPING = {
    "displacement": ["displacement", "engine displacement", "cubic capacity", "swept volume", "capacity"],
    "bore_mm": ["bore", "cylinder bore", "bore diameter", "bore size"],
    "stroke_mm": ["stroke", "piston stroke", "stroke length"],
    "compression_ratio": ["compression ratio", "compression", "comp ratio"],
    "power_hp": ["power", "power output", "horsepower", "max power", "maximum power", "bhp", "hp", "output"],
    "torque_nm": ["torque", "max torque", "maximum torque", "torque output"],
    "redline_rpm": ["redline", "red line", "rev limit", "maximum rpm", "max rpm"],
    "configuration": ["configuration", "engine type", "layout", "cylinder arrangement"],
    "block_material": ["cylinder block material", "block material", "cylinder block", "block"],
    "head_material": ["cylinder head material", "head material", "cylinder head"],
    "valvetrain": ["valvetrain", "valve train", "valves", "valve configuration"],
    "fuel_system": ["fuel system", "fuel delivery", "fuelsystem", "fuel type", "fuel injection"],
    "cooling": ["cooling", "cooling system"],
    "manufacturer": ["manufacturer", "made by", "produced by", "builder"],
    "production": ["production", "production years", "years produced", "built"],
    "successor": ["successor", "replaced by"],
    "predecessor": ["predecessor", "replaced"],
}

NUMERIC_COLS = ["displacement", "power_hp", "torque_nm", "bore_mm", "stroke_mm", "compression_ratio", "redline_rpm"]
TEXT_COLS = ["block_material", "head_material", "configuration"]

def normalize_spec_name(spec):
    spec_lower = spec.lower().strip()
    for standard_name, variations in SPEC_MAPPING.items():
        for variation in variations:
            if variation in spec_lower or spec_lower in variation:
                return standard_name
    return None

def extract_first_number(val):
    val = str(val).replace(",", "")
    range_match = re.findall(r'(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', val)
    if range_match:
        low, high = float(range_match[0][0]), float(range_match[0][1])
        return (low + high) / 2
    nums = re.findall(r'\d+\.?\d*', val)
    if nums:
        return float(nums[0])
    return None

def convert_power_to_hp(value_str):
    if pd.isna(value_str):
        return None
    val = str(value_str).lower().replace(",", "")
    number = extract_first_number(val)
    if number is None:
        return None
    if "kw" in val:
        converted = round(number * 1.341, 1)
        return converted if 30 < converted < 2000 else None
    elif "ps" in val or "cv" in val or "ch" in val:
        converted = round(number * 0.9863, 1)
        return converted if 30 < converted < 2000 else None
    elif "bhp" in val or "hp" in val or "horsepower" in val:
        return round(number, 1) if 30 < number < 2000 else None
    else:
        return round(number, 1) if 30 < number < 2000 else None

def convert_torque_to_nm(value_str):
    if pd.isna(value_str):
        return None
    val = str(value_str).lower().replace(",", "")
    number = extract_first_number(val)
    if number is None:
        return None
    if "lb" in val and "ft" in val:
        converted = round(number * 1.356, 1)
        return converted if converted < 5000 else None
    elif "kgm" in val or "kgf" in val:
        converted = round(number * 9.807, 1)
        return converted if converted < 5000 else None
    elif "nm" in val or "n·m" in val or "newton" in val:
        return round(number, 1) if number < 5000 else None
    else:
        return round(number, 1) if number < 5000 else None

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

    if "cu in" in val or "cuin" in val or "cubic in" in val:
        converted = round(number * 16.387, 1)
        return converted if 50 < converted < 100000 else None
    elif "l)" in val or " l" in val or "litre" in val or "liter" in val:
        converted = round(number * 1000, 1)
        return converted if 50 < converted < 100000 else None
    elif "cc" in val or "cm³" in val or "cm3" in val:
        return round(number, 1) if 50 < number < 100000 else None
    else:
        if number < 30:
            converted = round(number * 1000, 1)
            return converted if 50 < converted < 100000 else None
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
    elif "mm" in val:
        return round(number, 1) if number < 500 else None
    else:
        if number < 10:
            converted = round(number * 25.4, 1)
            return converted if converted < 500 else None
        return round(number, 1) if number < 500 else None

def convert_value(standard_name, value_str):
    if standard_name == "power_hp":
        return convert_power_to_hp(value_str)
    elif standard_name == "torque_nm":
        return convert_torque_to_nm(value_str)
    elif standard_name == "displacement":
        return convert_displacement_to_cc(value_str)
    elif standard_name in ["bore_mm", "stroke_mm"]:
        return convert_bore_stroke_to_mm(value_str)
    else:
        return value_str

def detect_shared_bad_values(normalized_df):
    for spec in ["power_hp", "torque_nm"]:
        if spec not in normalized_df.columns:
            continue

        for engine_name, group in normalized_df.groupby("engine"):
            if len(group) < 2:
                continue

            all_values = group[spec].dropna()
            if len(all_values) >= 2 and all_values.nunique() == 1:
                normalized_df.loc[group.index, spec] = None
                print(f"  Nulled shared {spec} {all_values.iloc[0]} for {engine_name} (all variants)")
                continue

            hp_variants = group[group["variant"].str.contains(r'\d+hp', case=False, na=False)]
            liter_variants = group[group["variant"].str.contains(r'\d+\.?\d*L$', na=False)]
            kw_variants = group[group["variant"].str.contains(r'\d+kW', case=False, na=False)]
            base_variants = group[group["variant"] == "base"]

            for subgroup_name, subgroup in [
                ("hp", hp_variants),
                ("liter", liter_variants),
                ("kw", kw_variants),
                ("base", base_variants)
            ]:
                if len(subgroup) < 2:
                    continue
                values = subgroup[spec].dropna()
                if len(values) < 2:
                    continue
                if values.nunique() == 1:
                    normalized_df.loc[subgroup.index, spec] = None
                    print(f"  Nulled shared {spec} {values.iloc[0]} for {engine_name} ({subgroup_name} variants)")

    return normalized_df

def cross_validate_specs(normalized_df):
    if "displacement" not in normalized_df.columns or "power_hp" not in normalized_df.columns:
        return normalized_df

    for idx, row in normalized_df.iterrows():
        disp = row.get("displacement")
        hp = row.get("power_hp")

        if pd.isna(disp) or pd.isna(hp):
            continue

        try:
            ratio = float(hp) / float(disp)
        except:
            continue

        if ratio > 0.5:
            print(f"  Cross-validate: nulled displacement {disp} for {row['engine_variant']} (ratio {round(ratio,3)} HP/cc)")
            normalized_df.at[idx, "displacement"] = None
        elif ratio < 0.02:
            print(f"  Cross-validate: nulled power_hp {hp} for {row['engine_variant']} (ratio {round(ratio,3)} HP/cc)")
            normalized_df.at[idx, "power_hp"] = None

    return normalized_df

def load_verified_seeds():
    seeds_path = os.path.join(BASE_DIR, "verified_seeds.csv")
    if not os.path.exists(seeds_path):
        return pd.DataFrame()
    df = pd.read_csv(seeds_path)
    df["engine_variant"] = df.apply(
        lambda r: f"{r['engine']} ({r['variant']})" if r['variant'] != "base" else r['engine'],
        axis=1
    )
    print(f"Loaded {len(df)} verified seed engines")
    return df

def merge_with_seeds(normalized_df, seeds_df):
    if seeds_df.empty:
        return normalized_df

    for col in NUMERIC_COLS:
        if col in normalized_df.columns:
            normalized_df[col] = pd.to_numeric(normalized_df[col], errors="coerce")

    for _, seed_row in seeds_df.iterrows():
        engine = seed_row["engine"]
        variant = seed_row["variant"]

        mask = (normalized_df["engine"] == engine) & (normalized_df["variant"] == variant)

        if mask.any():
            for col in NUMERIC_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    normalized_df.loc[mask, col] = float(seed_row[col])
            for col in TEXT_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    normalized_df.loc[mask, col] = str(seed_row[col])
            normalized_df.loc[mask, "confidence"] = "verified_manual"
            print(f"  Updated verified specs for {engine} ({variant})")
        else:
            new_row = {
                "engine": engine,
                "variant": variant,
                "engine_variant": seed_row["engine_variant"],
                "confidence": "verified_manual"
            }
            for col in NUMERIC_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    new_row[col] = float(seed_row[col])
            for col in TEXT_COLS:
                if col in seed_row and not pd.isna(seed_row[col]):
                    new_row[col] = str(seed_row[col])
            normalized_df = pd.concat([normalized_df, pd.DataFrame([new_row])], ignore_index=True)
            print(f"  Added verified engine: {engine} ({variant})")

    return normalized_df

def mark_epa_verified(normalized_df):
    epa_path = os.path.join(BASE_DIR, "engine_specs.csv")
    if not os.path.exists(epa_path):
        return normalized_df

    epa_df = pd.read_csv(epa_path)
    epa_engines = epa_df[epa_df["source"].str.contains("EPA", na=False)]["engine"].unique()

    for engine in epa_engines:
        mask = (normalized_df["engine"] == engine) & (normalized_df["confidence"] != "verified_manual")
        if mask.any():
            normalized_df.loc[mask, "confidence"] = "epa_verified"
            print(f"  EPA verified: {engine}")

    return normalized_df

def run_normalizer():
    print("Starting normalization...")
    logging.info("Normalization started")

    df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
    print(f"Loaded {len(df)} rows")

    has_variants = "variant" in df.columns

    normalized_rows = []
    unmapped = set()

    if has_variants:
        group_cols = ["engine", "variant"]
    else:
        group_cols = ["engine"]

    for keys, group in df.groupby(group_cols):
        if has_variants:
            engine_name, variant_name = keys
        else:
            engine_name = keys
            variant_name = "base"

        row = {
            "engine": engine_name,
            "variant": variant_name,
            "engine_variant": f"{engine_name} ({variant_name})" if variant_name != "base" else engine_name,
            "confidence": "wikipedia_single"
        }

        hp_in_variant = re.findall(r'(\d+)\s*hp', variant_name, re.IGNORECASE)
        liter_in_variant = re.findall(r'(\d+\.?\d*)L$', variant_name)

        if hp_in_variant:
            val = float(hp_in_variant[0])
            if 30 < val < 2000:
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

        if "power_hp" in row and row["power_hp"] is not None:
            if not (30 < float(row["power_hp"]) < 2000):
                row["power_hp"] = None

        if "displacement" in row and row["displacement"] is not None:
            if not (50 < float(row["displacement"]) < 100000):
                row["displacement"] = None

        if "torque_nm" in row and row["torque_nm"] is not None:
            if not (10 < float(row["torque_nm"]) < 5000):
                row["torque_nm"] = None

        normalized_rows.append(row)

    normalized_df = pd.DataFrame(normalized_rows)

    for col in NUMERIC_COLS:
        if col in normalized_df.columns:
            normalized_df[col] = pd.to_numeric(normalized_df[col], errors="coerce")

    print("Detecting shared bad values...")
    normalized_df = detect_shared_bad_values(normalized_df)

    print("Cross validating specs...")
    normalized_df = cross_validate_specs(normalized_df)

    print("Merging verified seeds...")
    seeds_df = load_verified_seeds()
    normalized_df = merge_with_seeds(normalized_df, seeds_df)

    print("Marking EPA verified engines...")
    normalized_df = mark_epa_verified(normalized_df)

    output_path = os.path.join(BASE_DIR, "engine_normalized.csv")
    normalized_df.to_csv(output_path, index=False)

    print(f"\nNormalized {len(normalized_df)} engine variants")
    print(f"Columns: {list(normalized_df.columns)}")

    # Show confidence breakdown
    if "confidence" in normalized_df.columns:
        print("\nConfidence breakdown:")
        print(normalized_df["confidence"].value_counts().to_string())

    logging.info(f"Normalization complete: {len(normalized_df)} variants")

    return normalized_df

if __name__ == "__main__":
    df = run_normalizer()
    print("\nEngines with both displacement AND power_hp:")
    if "power_hp" in df.columns and "displacement" in df.columns:
        both = df[["engine_variant", "displacement", "power_hp", "confidence"]].dropna(subset=["displacement", "power_hp"])
        print(f"Count: {len(both)}")
        print(both.to_string())
