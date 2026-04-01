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

# Map all variations to standard column names
SPEC_MAPPING = {
    # Displacement
    "displacement": ["displacement", "engine displacement", "cubic capacity", "swept volume", "capacity"],
    # Bore
    "bore_mm": ["bore", "cylinder bore", "bore diameter", "bore size"],
    # Stroke
    "stroke_mm": ["stroke", "piston stroke", "stroke length"],
    # Compression ratio
    "compression_ratio": ["compression ratio", "compression", "comp ratio"],
    # Power / HP
    "power_hp": ["power", "power output", "horsepower", "max power", "maximum power", "bhp", "hp", "output"],
    # Torque
    "torque_nm": ["torque", "max torque", "maximum torque", "torque output"],
    # RPM
    "redline_rpm": ["redline", "red line", "rev limit", "maximum rpm", "max rpm"],
    # Configuration
    "configuration": ["configuration", "engine type", "layout", "cylinder arrangement"],
    # Block material
    "block_material": ["cylinder block material", "block material", "cylinder block", "block"],
    # Head material
    "head_material": ["cylinder head material", "head material", "cylinder head"],
    # Valvetrain
    "valvetrain": ["valvetrain", "valve train", "valves", "valve configuration"],
    # Fuel system
    "fuel_system": ["fuel system", "fuel delivery", "fuelsystem", "fuel type", "fuel injection"],
    # Cooling
    "cooling": ["cooling", "cooling system"],
    # Manufacturer
    "manufacturer": ["manufacturer", "made by", "produced by", "builder"],
    # Production years
    "production": ["production", "production years", "years produced", "built"],
    # Successor
    "successor": ["successor", "replaced by"],
    # Predecessor
    "predecessor": ["predecessor", "replaced"],
}

def normalize_spec_name(spec):
    spec_lower = spec.lower().strip()
    for standard_name, variations in SPEC_MAPPING.items():
        for variation in variations:
            if variation in spec_lower or spec_lower in variation:
                return standard_name
    return None  # unmapped spec

def extract_numeric(value):
    if pd.isna(value):
        return None
    val = str(value)
    range_match = re.findall(r'(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', val)
    if range_match:
        low, high = float(range_match[0][0]), float(range_match[0][1])
        return (low + high) / 2
    nums = re.findall(r'\d+\.?\d*', val)
    if nums:
        return float(nums[0])
    return None

def run_normalizer():
    print("Starting normalization...")
    logging.info("Normalization started")

    df = pd.read_csv(os.path.join(BASE_DIR, "engine_specs.csv"))
    print(f"Loaded {len(df)} rows")

    normalized_rows = []
    unmapped = set()

    for engine_name, group in df.groupby("engine"):
        row = {"engine": engine_name}
        for _, spec_row in group.iterrows():
            standard = normalize_spec_name(str(spec_row["spec"]))
            if standard:
                if standard not in row:
                    row[standard] = spec_row["value"]
            else:
                unmapped.add(str(spec_row["spec"]))
        normalized_rows.append(row)

    normalized_df = pd.DataFrame(normalized_rows)

    # Save normalized dataset
    output_path = os.path.join(BASE_DIR, "engine_normalized.csv")
    normalized_df.to_csv(output_path, index=False)

    print(f"Normalized {len(normalized_df)} engines")
    print(f"Columns: {list(normalized_df.columns)}")
    print(f"Unmapped specs (top 20): {list(unmapped)[:20]}")
    logging.info(f"Normalization complete: {len(normalized_df)} engines, {len(normalized_df.columns)} columns")

    return normalized_df

if __name__ == "__main__":
    df = run_normalizer()
    print("\nSample data:")
    print(df[["engine", "manufacturer", "configuration", "block_material", "compression_ratio"]].head(10))
