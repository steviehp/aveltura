"""
tableau_export.py — Phase 12: Tableau / BI Export (Vehicle-First)

Generates three analysis-ready CSV files:
  export_vehicle_engine.csv  — PRIMARY: one row per vehicle/gen/trim with engine specs joined
  export_engine_specs.csv    — SECONDARY: one row per engine variant (deep specs)
  export_summary.csv         — aggregated stats by manufacturer, region, era, aspiration

Compatible with Tableau, Power BI, Google Sheets, Excel.
"""

import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
BASE_DIR   = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_manufacturer(engine_name):
    if not engine_name or pd.isna(engine_name):
        return "Unknown"
    return str(engine_name).split()[0]


def extract_region(manufacturer):
    jdm      = {"Toyota","Nissan","Honda","Subaru","Mitsubishi","Mazda","Lexus",
                "Acura","Infiniti","Isuzu","Suzuki","Hyundai","Kia","Genesis"}
    american = {"GM","Chevrolet","Ford","Dodge","Chrysler","Cadillac","Buick",
                "Jeep","Ram","Lincoln","Pontiac"}
    european = {"BMW","Mercedes","Mercedes-Benz","Audi","Porsche","Volkswagen",
                "Ferrari","Lamborghini","McLaren","Bugatti","Pagani","Koenigsegg",
                "Aston","Jaguar","Alfa","Volvo","Bentley","Rolls-Royce","Lotus",
                "Maserati","Lancia","FIAT","Renault","Peugeot","Seat"}
    if manufacturer in jdm:      return "JDM"
    if manufacturer in american: return "American"
    if manufacturer in european: return "European"
    return "Other"


def extract_engine_family(engine_name):
    if not engine_name or pd.isna(engine_name):
        return "Unknown"
    parts = str(engine_name).split()
    code  = parts[1] if len(parts) > 1 else parts[0]
    m = re.match(r'([A-Za-z]+)', code)
    return m.group(1).upper() if m else code


def classify_aspiration(engine_name, forced_induction=None):
    if not engine_name or pd.isna(engine_name):
        return "Naturally Aspirated"
    text = str(engine_name).lower()

    if forced_induction and not pd.isna(forced_induction):
        fi = str(forced_induction).lower()
        if "super" in fi: return "Supercharged"
        if "turbo" in fi: return "Turbocharged"

    turbo_signals = [
        "turbo", "dett", "det", "gte", "gts", "gtr", "gt-r",
        "wrx", "tfsi", "tdi", "tsi", "twin-turbo", "biturbo",
    ]
    if any(x in text for x in turbo_signals):
        return "Turbocharged"

    last_token = str(engine_name).split()[-1] if engine_name else ""
    if re.search(r'\d+[Tt]$', last_token):
        return "Turbocharged"

    if re.search(r'ej\s*(205|207|255|257)', text):
        return "Turbocharged"

    if re.search(r'fa\s*20\s*d', text):
        return "Turbocharged"

    if re.search(r'\bls[a9]\b', text):
        return "Supercharged"

    if any(x in text for x in ["hellcat", "demon", "redeye", "trackhawk",
                                "supercharg", "kompressor", "lsa"]):
        return "Supercharged"

    return "Naturally Aspirated"


def classify_era(year):
    if pd.isna(year): return "Unknown"
    y = int(year)
    if y < 1970: return "Classic (pre-1970)"
    if y < 1980: return "70s"
    if y < 1990: return "80s"
    if y < 2000: return "90s"
    if y < 2010: return "2000s"
    if y < 2020: return "2010s"
    return "2020s+"


def hp_per_litre(power_hp, displacement_cc):
    try:
        if pd.isna(power_hp) or pd.isna(displacement_cc) or displacement_cc == 0:
            return None
        return round(float(power_hp) / (float(displacement_cc) / 1000), 1)
    except Exception:
        return None


# ── Export 1: Vehicle-engine (PRIMARY) ───────────────────────────────────────

def export_vehicle_engine(apps_df, engine_df):
    """
    PRIMARY export — one row per vehicle/generation/trim.
    Joins engine deep specs (bore, stroke, compression) from engine_normalized.
    This is the main dataset for all BI analysis.
    """
    df = apps_df.copy()

    # Normalise numeric types
    for col in ["year_start", "year_end", "power_hp", "torque_nm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Displacement — may be in displacement or displacement_cc
    disp_col = "displacement" if "displacement" in df.columns else \
               "displacement_cc" if "displacement_cc" in df.columns else None
    if disp_col:
        df["displacement_cc"] = pd.to_numeric(df[disp_col], errors="coerce")
        df["displacement_l"]  = (df["displacement_cc"] / 1000).round(1)

    # Year span and era
    df["year_span"] = df.apply(
        lambda r: (int(r["year_end"]) - int(r["year_start"]) + 1)
        if pd.notna(r.get("year_start")) and pd.notna(r.get("year_end"))
        else None, axis=1
    )
    df["era"] = df["year_start"].apply(classify_era)

    # Manufacturer from vehicle or from existing column
    if "manufacturer" not in df.columns or df["manufacturer"].isna().all():
        df["manufacturer"] = df["engine"].apply(extract_manufacturer)
    if "region" not in df.columns or df["region"].isna().all():
        df["region"] = df["manufacturer"].apply(extract_region)

    # Aspiration
    df["aspiration"] = df["engine"].apply(classify_aspiration)

    # HP per litre
    df["hp_per_litre"] = df.apply(
        lambda r: hp_per_litre(r.get("power_hp"), r.get("displacement_cc")),
        axis=1
    )

    # Join engine deep specs if available
    if not engine_df.empty and "engine" in engine_df.columns:
        deep_cols = ["engine", "bore_mm", "stroke_mm", "compression_ratio",
                     "redline_rpm", "valvetrain", "fuel_system",
                     "block_material", "head_material", "configuration"]
        deep_cols = [c for c in deep_cols if c in engine_df.columns]
        # Use best confidence row per engine
        eng_lookup = engine_df.sort_values(
            "confidence",
            key=lambda x: x.map({"verified_manual":0,"epa_verified":1,"wikipedia_single":2}).fillna(3)
        ).drop_duplicates(subset=["engine"], keep="first")[deep_cols]

        df = df.merge(eng_lookup, on="engine", how="left", suffixes=("", "_eng"))

    # Select and order columns
    export_cols = [
        "vehicle", "manufacturer", "region", "generation", "trim",
        "engine", "aspiration", "year_start", "year_end", "year_span", "era",
        "power_hp", "torque_nm", "displacement_cc", "displacement_l",
        "hp_per_litre",
        "bore_mm", "stroke_mm", "compression_ratio", "redline_rpm",
        "valvetrain", "fuel_system", "configuration",
        "block_material", "head_material",
        "confidence", "notes", "source",
    ]
    export_cols = [c for c in export_cols if c in df.columns]
    df = df[export_cols]

    # Round numerics — coerce to numeric first to handle None/NaN
    for col in ["power_hp", "torque_nm", "displacement_cc", "displacement_l",
                "hp_per_litre", "bore_mm", "stroke_mm", "compression_ratio"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(1)

    path = os.path.join(EXPORT_DIR, "export_vehicle_engine.csv")
    df.to_csv(path, index=False)
    print(f"  export_vehicle_engine.csv — {len(df)} rows, {len(df.columns)} columns")
    return df


# ── Export 2: Engine specs (SECONDARY) ───────────────────────────────────────

def export_engine_specs(normalized_df):
    """
    SECONDARY export — one row per engine variant with deep specs.
    """
    df = normalized_df.copy()

    numeric_cols = ["displacement","power_hp","torque_nm","bore_mm",
                    "stroke_mm","compression_ratio","redline_rpm"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "displacement" in df.columns:
        df["displacement_l"] = (df["displacement"] / 1000).round(1)

    df["manufacturer"]  = df["engine"].apply(extract_manufacturer)
    df["region"]        = df["manufacturer"].apply(extract_region)
    df["engine_family"] = df["engine"].apply(extract_engine_family)
    df["aspiration"]    = df.apply(
        lambda r: classify_aspiration(
            r.get("engine", ""), r.get("forced_induction", None)
        ), axis=1
    )
    df["hp_per_litre"]  = df.apply(
        lambda r: hp_per_litre(r.get("power_hp"), r.get("displacement")),
        axis=1
    )

    export_cols = [
        "engine_variant","engine","variant",
        "manufacturer","region","engine_family","aspiration",
        "displacement","displacement_l","power_hp","torque_nm",
        "bore_mm","stroke_mm","compression_ratio","redline_rpm",
        "hp_per_litre","configuration","valvetrain","fuel_system",
        "block_material","head_material","production","confidence",
    ]
    export_cols = [c for c in export_cols if c in df.columns]
    df = df[export_cols]

    for col in ["displacement","power_hp","torque_nm","bore_mm",
                "stroke_mm","compression_ratio","hp_per_litre"]:
        if col in df.columns:
            df[col] = df[col].round(1)

    path = os.path.join(EXPORT_DIR, "export_engine_specs.csv")
    df.to_csv(path, index=False)
    print(f"  export_engine_specs.csv  — {len(df)} rows, {len(df.columns)} columns")
    return df


# ── Export 3: Summary stats ───────────────────────────────────────────────────

def export_summary(vehicle_df, engine_df):
    """Aggregated stats for dashboard cards and high-level views."""
    summaries = []

    primary = vehicle_df if not vehicle_df.empty else engine_df

    def _agg(df, group_col, rename_col):
        if group_col not in df.columns:
            return
        grp = df.groupby(group_col).agg(
            vehicle_count       = ("vehicle", "nunique") if "vehicle" in df.columns
                                  else ("engine", "nunique"),
            avg_power_hp        = ("power_hp", "mean"),
            max_power_hp        = ("power_hp", "max"),
            avg_displacement_cc = ("displacement_cc", "mean") if "displacement_cc" in df.columns else ("displacement", "mean") if "displacement" in df.columns else ("power_hp", "count"),
            avg_hp_per_litre    = ("hp_per_litre", "mean"),
        ).reset_index()
        grp["group_by"] = rename_col
        grp = grp.rename(columns={group_col: "group_value"})
        summaries.append(grp)

    _agg(primary, "manufacturer", "manufacturer")
    _agg(primary, "region",       "region")
    _agg(primary, "aspiration",   "aspiration")
    _agg(primary, "era",          "era")

    # Confidence breakdown from engine specs
    if not engine_df.empty and "confidence" in engine_df.columns:
        conf = engine_df.groupby("confidence").agg(
            engine_count        = ("engine", "nunique"),
            variant_count       = ("engine_variant", "count") if "engine_variant" in engine_df.columns
                                  else ("engine", "count"),
            avg_power_hp        = ("power_hp", "mean"),
        ).reset_index()
        conf["group_by"] = "confidence"
        conf = conf.rename(columns={"confidence": "group_value"})
        summaries.append(conf)

    if not summaries:
        print("  No summary data to export")
        return pd.DataFrame()

    summary_df = pd.concat(summaries, ignore_index=True)
    for col in summary_df.select_dtypes(include=[np.number]).columns:
        summary_df[col] = summary_df[col].round(1)

    path = os.path.join(EXPORT_DIR, "export_summary.csv")
    summary_df.to_csv(path, index=False)
    print(f"  export_summary.csv       — {len(summary_df)} rows")
    return summary_df


# ── Runner ────────────────────────────────────────────────────────────────────

def run_export():
    print(f"Starting Tableau export at {datetime.now()}")
    print(f"Output: {EXPORT_DIR}")

    apps_path   = os.path.join(BASE_DIR, "engine_applications.csv")
    engine_path = os.path.join(BASE_DIR, "engine_normalized.csv")

    apps_df   = pd.read_csv(apps_path)   if os.path.exists(apps_path)   else pd.DataFrame()
    engine_df = pd.read_csv(engine_path) if os.path.exists(engine_path) else pd.DataFrame()

    print(f"Loaded {len(apps_df)} applications, {len(engine_df)} engine variants")
    print("\nGenerating exports...")

    vehicle_export = export_vehicle_engine(apps_df, engine_df)
    engine_export  = export_engine_specs(engine_df)
    summary        = export_summary(vehicle_export, engine_export)

    print(f"\nDone — exports saved to {EXPORT_DIR}/")
    print("\nFiles:")
    for f in sorted(os.listdir(EXPORT_DIR)):
        path = os.path.join(EXPORT_DIR, f)
        size = os.path.getsize(path)
        print(f"  {f} — {size:,} bytes")

    if not vehicle_export.empty:
        print("\nVehicle breakdown by region:")
        if "region" in vehicle_export.columns:
            print(vehicle_export["region"].value_counts().to_string())
        print("\nAspiration breakdown:")
        if "aspiration" in vehicle_export.columns:
            print(vehicle_export["aspiration"].value_counts().to_string())
        print("\nTop 10 vehicles by HP/litre:")
        if "hp_per_litre" in vehicle_export.columns:
            show_cols = [c for c in ["vehicle","generation","trim","engine",
                         "hp_per_litre","power_hp","displacement_cc","displacement_l"]
                         if c in vehicle_export.columns]
            top = vehicle_export[show_cols].dropna(
                subset=["hp_per_litre"]
            ).nlargest(10, "hp_per_litre")
            print(top.to_string(index=False))


if __name__ == "__main__":
    run_export()
