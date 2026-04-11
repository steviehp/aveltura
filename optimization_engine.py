"""
optimization_engine.py — Vel Mathematical Optimization Engine

Handles two query types:
  1. Performance goal  — "I want 500whp from my Supra MK4"
  2. Attribute goal    — "I want better fuel economy / handling / reliability"

Pipeline:
  parse_query() → identify goal type, car, target
  pull_car_specs() → get baseline from Vel RAG data
  physics_engine() → calculate what's needed mathematically
  stats_layer() → regression on similar builds
  optimization_solver() → scipy minimize — best mod combo at min cost/risk
  format_output() → ranked plan + parts + install + supporting + issues + cost + timeline
"""

import os
import re
import json
import math
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "optimization.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Import knowledge base
import sys
sys.path.insert(0, BASE_DIR)
from mod_knowledge_base import (
    find_mods_by_engine, find_mods_by_hp_target,
    find_mods_by_tag, estimate_total_cost,
    TURBOS, SUPERCHARGERS, INTERCOOLERS,
    INJECTORS, FUEL_PUMPS, ECU_SYSTEMS,
    PISTONS, CONNECTING_RODS, HEAD_STUDS,
    COILOVERS, SWAY_BARS, TYRES, EXHAUSTS,
    BRAKES, COOLING, AERO, ALL_MODS
)

# ── Constants ─────────────────────────────────────────────────────────────────

# Drivetrain loss % by layout
DRIVETRAIN_LOSS = {
    "rwd": 0.15,   # 15% loss RWD
    "fwd": 0.13,   # 13% loss FWD
    "awd": 0.18,   # 18% loss AWD
    "4wd": 0.18,
}

# Known drivetrain layouts by platform keyword
PLATFORM_DRIVETRAIN = {
    "supra":      "rwd",
    "skyline":    "awd",
    "gtr":        "awd",
    "sti":        "awd",
    "wrx":        "awd",
    "evo":        "awd",
    "silvia":     "rwd",
    "180sx":      "rwd",
    "240sx":      "rwd",
    "mustang":    "rwd",
    "camaro":     "rwd",
    "corvette":   "rwd",
    "m3":         "rwd",
    "civic":      "fwd",
    "integra":    "fwd",
    "s2000":      "rwd",
    "nsx":        "rwd",
    "rx7":        "rwd",
    "rx-7":       "rwd",
    "miata":      "rwd",
    "86":         "rwd",
    "brz":        "rwd",
}

# HP per litre benchmarks for aspirated engines
ASPIRATION_HP_PER_LITRE = {
    "naturally_aspirated": 75,
    "turbocharged":        130,
    "supercharged":        120,
}

# Safe boost PSI for stock compression ratios
SAFE_BOOST_TABLE = {
    # compression_ratio: max_safe_psi on pump gas
    11.0: 4,
    10.5: 6,
    10.0: 8,
    9.5:  10,
    9.0:  13,
    8.5:  16,
    8.0:  20,
    7.5:  24,
    7.0:  28,
}

# Injector sizing: cc/min needed per HP (on pump gas E10)
CC_PER_HP_PUMP  = 5.5
CC_PER_HP_E85   = 8.5

# Fuel pump flow needed: cc/min per HP
PUMP_CC_PER_HP  = 6.0

# Intercooler sizing: HP per 100cc of core volume (rough)
IC_HP_PER_100CC = 12

# Aero drag reduction per modification type
AERO_CD_REDUCTION = {
    "lower_ride_height_25mm": 0.012,
    "underbody_panels":       0.015,
    "front_splitter":         0.008,
    "rear_wing":             -0.02,   # wing adds drag
    "mirrors_removal":        0.004,
}

# Rolling resistance coefficient by tyre type
RRC = {
    "standard":  0.010,
    "eco":       0.007,
    "performance": 0.011,
    "semi_slick": 0.013,
}

# ── Goal detection ─────────────────────────────────────────────────────────────

PERFORMANCE_KEYWORDS = [
    "whp", "wheel horsepower", "hp", "horsepower", "power",
    "boost", "turbo", "supercharge", "fast", "quick", "accelerat",
    "drag", "quarter mile", "track", "race"
]

EFFICIENCY_KEYWORDS = [
    "fuel economy", "fuel efficient", "mpg", "gas mileage", "economy",
    "efficient", "save fuel", "mileage", "consumption"
]

HANDLING_KEYWORDS = [
    "handling", "cornering", "grip", "steering", "suspension",
    "turn in", "corner", "oversteer", "understeer", "balance",
    "autocross", "canyon", "twisty"
]

RELIABILITY_KEYWORDS = [
    "reliable", "reliability", "last longer", "durability",
    "daily driver", "long lasting", "maintainable"
]


def detect_goal_type(query):
    """
    Returns (goal_type, target_value) tuple.
    goal_type: 'performance' | 'efficiency' | 'handling' | 'reliability' | 'unknown'
    target_value: numeric target if performance, None otherwise
    """
    q = query.lower()

    # Check for HP target
    hp_match = re.search(
        r'(\d{2,4})\s*(?:whp|wheel\s*hp|wheel\s*horsepower|hp|horsepower|bhp|ps)',
        q
    )
    if hp_match:
        return "performance", int(hp_match.group(1))

    if any(kw in q for kw in PERFORMANCE_KEYWORDS):
        return "performance", None

    if any(kw in q for kw in EFFICIENCY_KEYWORDS):
        return "efficiency", None

    if any(kw in q for kw in HANDLING_KEYWORDS):
        return "handling", None

    if any(kw in q for kw in RELIABILITY_KEYWORDS):
        return "reliability", None

    return "unknown", None


def extract_car_from_query(query):
    """
    Extract car name from query.
    Returns best match string or None.
    """
    q = query.lower()

    # Common car patterns
    patterns = [
        r'(toyota\s+supra(?:\s+(?:mk[1-5]|a\d{2}|jzz\d{2}))?)',
        r'(nissan\s+skyline(?:\s+(?:r3[2-5]|gt-?r))?)',
        r'(nissan\s+(?:silvia|180sx|240sx)(?:\s+(?:s1[3-5]))?)',
        r'(subaru\s+(?:wrx|sti|impreza)(?:\s+sti)?)',
        r'(mitsubishi\s+(?:lancer|evo(?:lution)?)(?:\s+[ivx]+|\s+\d+)?)',
        r'(honda\s+(?:civic|s2000|nsx|integra)(?:\s+type.?r)?)',
        r'(ford\s+mustang(?:\s+(?:gt|gt350|gt500|shelby|cobra))?)',
        r'(bmw\s+m[2-8](?:\s+(?:e\d{2}|f\d{2}|g\d{2}))?)',
        r'(chevrolet\s+(?:corvette|camaro)(?:\s+(?:ss|z28|zl1|z06|zo6))?)',
        r'(mazda\s+rx-?7(?:\s+fd)?)',
        r'(mazda\s+miata(?:\s+(?:na|nb|nc|nd))?)',
        r'(porsche\s+(?:911|cayman|boxster)(?:\s+\d{3})?)',
    ]

    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return m.group(1).title()

    # Generic fallback — look for known keywords
    car_keywords = {
        "supra": "Toyota Supra",
        "skyline": "Nissan Skyline",
        "gtr": "Nissan GT-R",
        "gt-r": "Nissan GT-R",
        "silvia": "Nissan Silvia",
        "240sx": "Nissan 240SX",
        "180sx": "Nissan 180SX",
        "wrx sti": "Subaru WRX STI",
        "wrx": "Subaru WRX",
        "sti": "Subaru STI",
        "evo": "Mitsubishi Lancer Evolution",
        "lancer": "Mitsubishi Lancer",
        "s2000": "Honda S2000",
        "civic": "Honda Civic",
        "integra": "Honda Integra",
        "mustang": "Ford Mustang",
        "camaro": "Chevrolet Camaro",
        "corvette": "Chevrolet Corvette",
        "m3": "BMW M3",
        "m4": "BMW M4",
        "rx7": "Mazda RX-7",
        "rx-7": "Mazda RX-7",
        "miata": "Mazda Miata",
        "911": "Porsche 911",
    }
    for kw, name in car_keywords.items():
        if kw in q:
            return name

    return None


def extract_engine_from_query(query):
    """Extract engine code from query if mentioned directly."""
    q = query.upper()
    engine_patterns = [
        r'2JZ-?GTE?', r'2JZ-?GE',
        r'RB26DETT?', r'RB25DET', r'RB20DET',
        r'SR20DET', r'CA18DET',
        r'EJ25[57]?', r'EJ20[57]?', r'FA20',
        r'4G63T?', r'6G72',
        r'K20[ACZ]?', r'K24',
        r'B18[BC]?', r'B16',
        r'F20C', r'F22C',
        r'LS[1-9]', r'LS7', r'LS9', r'LSA',
        r'COYOTE', r'5\.0',
        r'S54', r'S55', r'S58', r'N54', r'N55',
        r'VR38DETT?',
        r'13B-?REW?',
    ]
    for pattern in engine_patterns:
        m = re.search(pattern, q)
        if m:
            return m.group(0)
    return None


# ── Car spec lookup ───────────────────────────────────────────────────────────

def load_car_specs(car_name=None, engine_name=None):
    """
    Pull baseline specs from engine_applications.csv and engine_normalized.csv.
    Returns dict with stock specs.
    """
    specs = {
        "car":          car_name or "Unknown",
        "engine":       engine_name or "Unknown",
        "stock_hp":     None,
        "stock_torque": None,
        "displacement": None,
        "compression":  None,
        "config":       None,
        "aspiration":   "naturally_aspirated",
        "drivetrain":   "rwd",
        "weight_kg":    None,
        "confidence":   "estimated",
    }

    # Load applications
    apps_path = os.path.join(BASE_DIR, "engine_applications.csv")
    if os.path.exists(apps_path) and car_name:
        apps_df = pd.read_csv(apps_path)
        car_lower = car_name.lower()
        match = apps_df[apps_df["vehicle"].str.lower().str.contains(
            car_lower.split()[0], na=False
        )]
        if not match.empty:
            row = match.iloc[0]
            specs["engine"]       = str(row.get("engine", engine_name or "Unknown"))
            specs["stock_hp"]     = row.get("power_hp")
            specs["stock_torque"] = row.get("torque_nm")
            if pd.notna(row.get("displacement")):
                specs["displacement"] = float(row["displacement"])
            if pd.notna(row.get("confidence")):
                specs["confidence"] = str(row["confidence"])
            if engine_name is None:
                engine_name = specs["engine"]

    # Load engine normalized for deep specs
    eng_path = os.path.join(BASE_DIR, "engine_normalized.csv")
    if os.path.exists(eng_path) and engine_name:
        eng_df = pd.read_csv(eng_path)
        eng_lower = engine_name.upper()
        match = eng_df[eng_df["engine"].str.upper().str.contains(
            eng_lower.split()[0], na=False
        )]
        if not match.empty:
            row = match.iloc[0]
            if specs["stock_hp"] is None and pd.notna(row.get("power_hp")):
                specs["stock_hp"] = float(row["power_hp"])
            if specs["displacement"] is None and pd.notna(row.get("displacement")):
                specs["displacement"] = float(row["displacement"])
            if pd.notna(row.get("compression_ratio")):
                specs["compression"] = float(row["compression_ratio"])
            if pd.notna(row.get("configuration")):
                specs["config"] = str(row["configuration"])

    # Detect drivetrain from car name
    if car_name:
        for kw, layout in PLATFORM_DRIVETRAIN.items():
            if kw in car_name.lower():
                specs["drivetrain"] = layout
                break

    # Detect aspiration from engine name
    eng = (specs["engine"] or "").lower()
    if any(x in eng for x in ["gte", "dett", "det", "turbo", "t "]):
        specs["aspiration"] = "turbocharged"
    elif any(x in eng for x in ["lsa", "ls9", "lsa", "supercharg"]):
        specs["aspiration"] = "supercharged"

    return specs


# ── Physics engine ────────────────────────────────────────────────────────────

def calc_crank_hp_from_whp(whp, drivetrain="rwd"):
    """Convert wheel HP target to crank HP needed."""
    loss = DRIVETRAIN_LOSS.get(drivetrain, 0.15)
    return round(whp / (1 - loss))


def calc_safe_boost(compression_ratio):
    """Return safe max boost PSI for a given compression ratio on pump gas."""
    if not compression_ratio:
        return 12  # default safe assumption
    for cr, psi in sorted(SAFE_BOOST_TABLE.items()):
        if compression_ratio >= cr:
            return psi
    return 8


def calc_injector_size_needed(hp_target, cylinders=6, fuel="pump"):
    """
    Calculate minimum injector size (cc/min) for HP target.
    Assumes 80% duty cycle max.
    """
    cc_per_hp = CC_PER_HP_E85 if fuel == "e85" else CC_PER_HP_PUMP
    total_cc  = hp_target * cc_per_hp
    per_injector = total_cc / cylinders
    # Add 20% headroom for 80% duty cycle
    return round(per_injector / 0.80)


def calc_fuel_pump_needed(hp_target, fuel="pump"):
    """Calculate fuel pump flow needed in LPH."""
    cc_per_min = hp_target * PUMP_CC_PER_HP
    lph        = (cc_per_min * 60) / 1000
    return round(lph * 1.2)  # 20% safety margin


def calc_turbo_hp_potential(displacement_cc, boost_psi, volumetric_efficiency=0.85):
    """
    Estimate HP potential from displacement + boost.
    Simple thermodynamic model:
    HP = (displacement_L * boost_absolute_bar * VE * RPM) / constant
    Uses simplified BMEP approach.
    """
    displacement_L    = displacement_cc / 1000
    ambient_bar       = 1.013
    boost_bar         = boost_psi * 0.0689476
    absolute_pressure = ambient_bar + boost_bar
    pressure_ratio    = absolute_pressure / ambient_bar

    # Estimated HP using pressure ratio and displacement
    # NA baseline ~90hp/L for most performance engines
    na_hp_per_litre = 90
    na_hp           = displacement_L * na_hp_per_litre
    boosted_hp      = na_hp * pressure_ratio * volumetric_efficiency

    return round(boosted_hp)


def calc_hp_gap(stock_hp, target_whp, drivetrain="rwd"):
    """Calculate HP gap and required crank HP."""
    target_crank = calc_crank_hp_from_whp(target_whp, drivetrain)
    gap          = target_crank - (stock_hp or 0)
    return {
        "stock_hp":      stock_hp or 0,
        "target_whp":    target_whp,
        "target_crank":  target_crank,
        "hp_gap":        gap,
        "drivetrain_loss_pct": int(DRIVETRAIN_LOSS.get(drivetrain, 0.15) * 100),
    }


def calc_fuel_efficiency_gains(mods_applied):
    """
    Calculate theoretical fuel efficiency improvement from a list of mods.
    Returns estimated MPG improvement percentage.
    """
    total_gain_pct = 0.0

    for mod in mods_applied:
        tags = mod.get("tags", [])
        if "eco" in tags or "fuel_efficiency" in tags:
            # Tyre rolling resistance reduction
            if mod.get("category") == "tyre":
                total_gain_pct += 3.0  # ~3% from low RRC tyres
        if "coilover" in tags or mod.get("category") == "coilover":
            # Lowering 25mm reduces drag ~2%
            total_gain_pct += 2.0
        if "exhaust" in mod.get("category", ""):
            # Better exhaust flow reduces pumping losses ~1-2%
            total_gain_pct += 1.5
        if "intake" in tags:
            total_gain_pct += 1.0

    return round(total_gain_pct, 1)


# ── Optimization solver ───────────────────────────────────────────────────────

def solve_performance_build(specs, target_whp, budget_usd=None):
    """
    Given car specs and target WHP, return optimal mod plan.
    Uses physics constraints + knowledge base lookup.
    """
    plan = {
        "goal":              f"{target_whp}whp",
        "car":               specs["car"],
        "engine":            specs["engine"],
        "stock_hp":          specs["stock_hp"],
        "drivetrain":        specs["drivetrain"],
        "gap":               calc_hp_gap(specs["stock_hp"], target_whp, specs["drivetrain"]),
        "mods":              [],
        "supporting_mods":   [],
        "known_issues":      [],
        "internals_needed":  False,
        "cost_breakdown":    [],
        "total_cost_low":    0,
        "total_cost_high":   0,
        "confidence":        0,
        "phases":            [],
        "warnings":          [],
    }

    engine     = specs["engine"] or ""
    target_crank = plan["gap"]["target_crank"]
    compression  = specs.get("compression") or 9.0
    displacement = specs.get("displacement") or 3000
    cylinders    = 6  # default — improve later
    drivetrain   = specs["drivetrain"]

    # ── Detect cylinder count from engine ────────────────────────────────────
    config = (specs.get("config") or "").lower()
    if "v8" in config or "v-8" in config:
        cylinders = 8
    elif "v6" in config or "v-6" in config:
        cylinders = 6
    elif "inline-4" in config or "i4" in config or "4-cyl" in config:
        cylinders = 4
    elif "inline-6" in config or "i6" in config or "6-cyl" in config:
        cylinders = 6
    elif "v12" in config:
        cylinders = 12
    elif "rotary" in config or "wankel" in config:
        cylinders = 2  # rotor equivalent for injector calc

    # ── Safe boost check ──────────────────────────────────────────────────────
    safe_boost = calc_safe_boost(compression)
    potential_at_safe_boost = calc_turbo_hp_potential(displacement, safe_boost)

    if target_crank > potential_at_safe_boost * 1.1:
        plan["internals_needed"] = True
        plan["warnings"].append(
            f"Target power ({target_crank}hp crank) exceeds safe stock boost potential "
            f"({potential_at_safe_boost}hp at {safe_boost}psi). "
            f"Forged internals required for reliability."
        )

    # ── 1. Forced induction ───────────────────────────────────────────────────
    if specs["aspiration"] == "naturally_aspirated":
        # NA to turbo conversion — find appropriate turbo
        turbo_candidates = [t for t in TURBOS
                            if t["min_hp"] <= target_crank <= t["max_hp"]]
        # Filter by engine compatibility
        engine_turbos = [t for t in turbo_candidates
                         if any(e.upper() in engine.upper() or engine.upper() in e.upper()
                                or "UNIVERSAL" in [x.upper() for x in t.get("compatible_engines",[])]
                                for e in t.get("compatible_engines", []))]
        if not engine_turbos:
            engine_turbos = turbo_candidates  # fallback to any compatible
        if engine_turbos:
            # Pick smallest that meets target (best spool)
            engine_turbos.sort(key=lambda t: t["max_hp"])
            chosen_turbo = engine_turbos[0]
            plan["mods"].append({
                "rank":            1,
                "name":            chosen_turbo["name"],
                "category":        "turbo",
                "hp_gain":         f"+{target_crank - (specs['stock_hp'] or 0)}hp (primary contributor)",
                "install_location": chosen_turbo["install_location"],
                "cost_low":        chosen_turbo["cost_usd"][0],
                "cost_high":       chosen_turbo["cost_usd"][1],
                "known_issues":    chosen_turbo["known_issues"],
                "confidence_pct":  88,
            })
            plan["supporting_mods"].extend(chosen_turbo.get("supporting_mods", []))

    elif specs["aspiration"] == "turbocharged":
        # Already turbocharged — find turbo upgrade
        turbo_candidates = [t for t in TURBOS
                            if t["max_hp"] >= target_crank]
        engine_turbos = [t for t in turbo_candidates
                         if any(e.upper() in engine.upper()
                                for e in t.get("compatible_engines", []))]
        if not engine_turbos:
            engine_turbos = turbo_candidates[:3]
        if engine_turbos:
            engine_turbos.sort(key=lambda t: t["max_hp"])
            chosen_turbo = engine_turbos[0]
            plan["mods"].append({
                "rank":            1,
                "name":            chosen_turbo["name"],
                "category":        "turbo_upgrade",
                "hp_gain":         f"supports up to {chosen_turbo['max_hp']}hp",
                "install_location": chosen_turbo["install_location"],
                "cost_low":        chosen_turbo["cost_usd"][0],
                "cost_high":       chosen_turbo["cost_usd"][1],
                "known_issues":    chosen_turbo["known_issues"],
                "confidence_pct":  90,
            })
            plan["supporting_mods"].extend(chosen_turbo.get("supporting_mods", []))

    # ── 2. Intercooler ────────────────────────────────────────────────────────
    ic_candidates = [ic for ic in INTERCOOLERS
                     if ic.get("max_hp", 0) >= target_crank]
    # Engine-specific first
    engine_ics = [ic for ic in ic_candidates
                  if any(e.upper() in engine.upper()
                         for e in ic.get("compatible_engines", []))]
    if not engine_ics:
        engine_ics = [ic for ic in ic_candidates
                      if "universal" in [e.lower() for e in ic.get("compatible_engines", [])]]
    if engine_ics:
        chosen_ic = engine_ics[0]
        plan["mods"].append({
            "rank":            2,
            "name":            chosen_ic["name"],
            "category":        "intercooler",
            "hp_gain":         "prevents heat soak, maintains power",
            "install_location": chosen_ic["install_location"],
            "cost_low":        chosen_ic["cost_usd"][0],
            "cost_high":       chosen_ic["cost_usd"][1],
            "known_issues":    chosen_ic.get("known_issues", []),
            "confidence_pct":  95,
        })

    # ── 3. Fuel system ────────────────────────────────────────────────────────
    injector_cc = calc_injector_size_needed(target_crank, cylinders)
    pump_lph    = calc_fuel_pump_needed(target_crank)

    # Find injectors
    inj_candidates = [i for i in INJECTORS
                      if i["flow_cc_min"] >= injector_cc]
    if inj_candidates:
        inj_candidates.sort(key=lambda i: i["flow_cc_min"])
        chosen_inj = inj_candidates[0]
        plan["mods"].append({
            "rank":            3,
            "name":            chosen_inj["name"],
            "category":        "injector",
            "hp_gain":         f"enables target fueling ({injector_cc}cc/min needed)",
            "install_location": chosen_inj["install_location"],
            "cost_low":        chosen_inj["cost_usd"][0],
            "cost_high":       chosen_inj["cost_usd"][1],
            "known_issues":    chosen_inj.get("known_issues", []),
            "confidence_pct":  95,
        })

    # Find fuel pump
    pump_candidates = [p for p in FUEL_PUMPS
                       if p.get("flow_lph", 0) >= pump_lph * 0.8]
    if pump_candidates:
        pump_candidates.sort(key=lambda p: p.get("flow_lph", 0))
        chosen_pump = pump_candidates[0]
        plan["mods"].append({
            "rank":            4,
            "name":            chosen_pump["name"],
            "category":        "fuel_pump",
            "hp_gain":         f"enables target fuel flow ({pump_lph}lph needed)",
            "install_location": chosen_pump["install_location"],
            "cost_low":        chosen_pump["cost_usd"][0],
            "cost_high":       chosen_pump["cost_usd"][1],
            "known_issues":    chosen_pump.get("known_issues", []),
            "confidence_pct":  95,
        })

    # ── 4. ECU ────────────────────────────────────────────────────────────────
    # Engine-specific ECU
    ecu_candidates = [e for e in ECU_SYSTEMS
                      if any(engine.upper() in p.upper() or
                             specs["car"].upper() in p.upper()
                             for p in e.get("compatible_platforms", []))]
    # Sort platform-specific ECUs first, prefer plug-in over wire-in
    ecu_candidates.sort(key=lambda e: 0 if e.get("type") == "standalone" and "plug" in e["name"].lower() else 1)
    if not ecu_candidates:
        # Prefer Link G4X as universal fallback (best JDM support)
        ecu_candidates = [e for e in ECU_SYSTEMS if "Link" in e["name"]]
    if not ecu_candidates:
        ecu_candidates = [e for e in ECU_SYSTEMS
                          if "universal" in [p.lower() for p in e.get("compatible_platforms", [])]]
    if ecu_candidates:
        chosen_ecu = ecu_candidates[0]
        plan["mods"].append({
            "rank":            5,
            "name":            chosen_ecu["name"],
            "category":        "ecu",
            "hp_gain":         "required — safe tuning of all mods",
            "install_location": chosen_ecu["install_location"],
            "cost_low":        chosen_ecu["cost_usd"][0],
            "cost_high":       chosen_ecu["cost_usd"][1],
            "known_issues":    chosen_ecu.get("known_issues", []),
            "confidence_pct":  99,
        })

    # ── 5. Internals (if needed) ──────────────────────────────────────────────
    if plan["internals_needed"]:
        # Pistons
        piston_candidates = [p for p in PISTONS
                             if any(engine.upper().split('-')[0] in e.upper()
                                    for e in p.get("compatible_engines", []))]
        if piston_candidates:
            plan["mods"].append({
                "rank":            6,
                "name":            piston_candidates[0]["name"],
                "category":        "piston",
                "hp_gain":         f"required for reliability above {potential_at_safe_boost}hp",
                "install_location": piston_candidates[0]["install_location"],
                "cost_low":        piston_candidates[0]["cost_usd"][0],
                "cost_high":       piston_candidates[0]["cost_usd"][1],
                "known_issues":    piston_candidates[0].get("known_issues", []),
                "confidence_pct":  90,
            })

        # Head studs
        stud_candidates = [s for s in HEAD_STUDS
                           if any(engine.upper().split('-')[0] in e.upper()
                                  for e in s.get("compatible_engines", []))]
        if stud_candidates:
            plan["mods"].append({
                "rank":            7,
                "name":            stud_candidates[0]["name"],
                "category":        "head_stud",
                "hp_gain":         "prevents head lift at high boost",
                "install_location": stud_candidates[0]["install_location"],
                "cost_low":        stud_candidates[0]["cost_usd"][0],
                "cost_high":       stud_candidates[0]["cost_usd"][1],
                "known_issues":    stud_candidates[0].get("known_issues", []),
                "confidence_pct":  95,
            })

    # ── 6. Exhaust ────────────────────────────────────────────────────────────
    exhaust_candidates = [e for e in EXHAUSTS
                          if any(engine.upper().split('-')[0] in eng.upper()
                                 for eng in e.get("compatible_engines", [])) or
                          any(specs["car"].upper().split()[0] in p.upper()
                              for p in e.get("compatible_platforms", []))]
    if exhaust_candidates:
        plan["mods"].append({
            "rank":            8,
            "name":            exhaust_candidates[0]["name"],
            "category":        "exhaust",
            "hp_gain":         f"+{exhaust_candidates[0].get('hp_gain_estimate', 15)}-25hp",
            "install_location": exhaust_candidates[0]["install_location"],
            "cost_low":        exhaust_candidates[0]["cost_usd"][0],
            "cost_high":       exhaust_candidates[0]["cost_usd"][1],
            "known_issues":    exhaust_candidates[0].get("known_issues", []),
            "confidence_pct":  80,
        })

    # ── Cost rollup ───────────────────────────────────────────────────────────
    total_low  = sum(m["cost_low"]  for m in plan["mods"])
    total_high = sum(m["cost_high"] for m in plan["mods"])
    plan["total_cost_low"]  = total_low
    plan["total_cost_high"] = total_high

    # Tune cost
    plan["mods"].append({
        "rank":            99,
        "name":            "Professional Dyno Tune",
        "category":        "tune",
        "hp_gain":         "optimises all mods — mandatory",
        "install_location": "dyno shop, 1-2 day session",
        "cost_low":        500,
        "cost_high":       1200,
        "known_issues":    ["do not operate modified vehicle before tune"],
        "confidence_pct":  99,
    })
    plan["total_cost_low"]  += 500
    plan["total_cost_high"] += 1200

    # ── Deduplicate supporting mods ───────────────────────────────────────────
    primary_mods = {m["category"] for m in plan["mods"]}
    skip_keywords = ["intercooler", "injector", "fuel pump", "ecu", "tune",
                     "standalone", "fmic", "wastegate" if "wastegate" not in primary_mods else ""]
    plan["supporting_mods"] = list(dict.fromkeys([
        s for s in plan["supporting_mods"]
        if not any(skip.lower() in s.lower() for skip in skip_keywords if skip)
    ]))

    # ── Phased timeline ───────────────────────────────────────────────────────
    plan["phases"] = build_phases(plan["mods"], plan["total_cost_low"])

    # ── Confidence ────────────────────────────────────────────────────────────
    scores = [m["confidence_pct"] for m in plan["mods"]]
    plan["confidence"] = round(sum(scores) / len(scores)) if scores else 70

    return plan


def solve_efficiency_build(specs):
    """Return optimal mod plan for fuel efficiency goal."""
    plan = {
        "goal":         "improved fuel efficiency",
        "car":          specs["car"],
        "engine":       specs["engine"],
        "mods":         [],
        "supporting_mods": [],
        "known_issues": [],
        "cost_breakdown": [],
        "total_cost_low":  0,
        "total_cost_high": 0,
        "estimated_mpg_gain_pct": 0,
        "phases": [],
    }

    # 1. Low rolling resistance tyres
    eco_tyres = [t for t in TYRES if "eco" in t.get("tags", [])]
    if eco_tyres:
        t = eco_tyres[0]
        plan["mods"].append({
            "rank": 1,
            "name": t["name"],
            "category": "tyre",
            "benefit": "3-5% reduction in rolling resistance",
            "install_location": "all 4 wheels, replace current tyres",
            "cost_low":  t["cost_usd_per_tyre"][0] * 4,
            "cost_high": t["cost_usd_per_tyre"][1] * 4,
            "known_issues": [t.get("notes", "")],
        })

    # 2. Coilovers — lower ride height reduces drag
    coil_candidates = [c for c in COILOVERS if "street" in c.get("tags", [])]
    if not coil_candidates:
        coil_candidates = COILOVERS[:1]
    if coil_candidates:
        c = coil_candidates[0]
        plan["mods"].append({
            "rank": 2,
            "name": c["name"] + " (lowered 25-30mm)",
            "category": "coilover",
            "benefit": "reduces drag coefficient ~2-3%, improves aero",
            "install_location": c["install_location"],
            "cost_low":  c["cost_usd"][0],
            "cost_high": c["cost_usd"][1],
            "known_issues": c.get("known_issues", []),
        })

    # 3. Cat-back exhaust — reduces pumping losses
    exhaust_candidates = [e for e in EXHAUSTS
                          if any(specs["car"].upper().split()[0] in p.upper()
                                 for p in e.get("compatible_platforms", []))]
    if exhaust_candidates:
        e = exhaust_candidates[0]
        plan["mods"].append({
            "rank": 3,
            "name": e["name"],
            "category": "exhaust",
            "benefit": "reduces back pressure, improves thermal efficiency 1-2%",
            "install_location": e["install_location"],
            "cost_low":  e["cost_usd"][0],
            "cost_high": e["cost_usd"][1],
            "known_issues": e.get("known_issues", []),
        })

    # 4. Oil cooler — maintains optimal oil viscosity
    oil_cooler = [c for c in COOLING if c.get("type") == "oil cooler"]
    if oil_cooler:
        oc = oil_cooler[0]
        plan["mods"].append({
            "rank": 4,
            "name": oc["name"],
            "category": "cooling",
            "benefit": "maintains optimal oil temp, reduces friction losses",
            "install_location": oc["install_location"],
            "cost_low":  oc["cost_usd"][0],
            "cost_high": oc["cost_usd"][1],
            "known_issues": oc.get("known_issues", []),
        })

    # Totals
    plan["total_cost_low"]  = sum(m["cost_low"]  for m in plan["mods"])
    plan["total_cost_high"] = sum(m["cost_high"] for m in plan["mods"])
    plan["estimated_mpg_gain_pct"] = 8  # conservative overall estimate
    plan["phases"] = build_phases(plan["mods"], plan["total_cost_low"])

    return plan


def solve_handling_build(specs):
    """Return optimal mod plan for handling goal."""
    plan = {
        "goal":         "improved handling",
        "car":          specs["car"],
        "engine":       specs["engine"],
        "mods":         [],
        "supporting_mods": [],
        "known_issues": [],
        "total_cost_low":  0,
        "total_cost_high": 0,
        "phases":       [],
    }

    # 1. Coilovers
    coil_candidates = [c for c in COILOVERS
                       if any(specs["car"].upper().split()[-1] in p.upper()
                              for p in c.get("compatible_platforms", []))]
    if not coil_candidates:
        coil_candidates = [c for c in COILOVERS if "street_track" in c.get("tags", [])]
    if coil_candidates:
        c = coil_candidates[0]
        plan["mods"].append({
            "rank": 1,
            "name": c["name"],
            "category": "coilover",
            "benefit": "lower CoG, adjustable damping, improved response",
            "install_location": c["install_location"],
            "cost_low":  c["cost_usd"][0],
            "cost_high": c["cost_usd"][1],
            "known_issues": c.get("known_issues", []),
        })

    # 2. Sway bars
    if SWAY_BARS:
        sb = SWAY_BARS[0]
        plan["mods"].append({
            "rank": 2,
            "name": sb["name"],
            "category": "sway_bar",
            "benefit": "reduces body roll, improves flat cornering",
            "install_location": sb["install_location"],
            "cost_low":  sb["cost_usd"][0],
            "cost_high": sb["cost_usd"][1],
            "known_issues": sb.get("known_issues", []),
        })

    # 3. Performance tyres
    perf_tyres = [t for t in TYRES if "performance" in t.get("tags", [])]
    if perf_tyres:
        t = perf_tyres[0]
        plan["mods"].append({
            "rank": 3,
            "name": t["name"],
            "category": "tyre",
            "benefit": "improved grip, shorter braking, better turn-in",
            "install_location": "all 4 wheels",
            "cost_low":  t["cost_usd_per_tyre"][0] * 4,
            "cost_high": t["cost_usd_per_tyre"][1] * 4,
            "known_issues": [t.get("notes", "")],
        })

    # 4. Big brake kit
    bbk_candidates = [b for b in BRAKES if b.get("type") == "big brake kit"]
    if bbk_candidates:
        b = bbk_candidates[0]
        plan["mods"].append({
            "rank": 4,
            "name": b["name"],
            "category": "brake",
            "benefit": "improved stopping power, better pedal feel, reduced fade",
            "install_location": b["install_location"],
            "cost_low":  b["cost_usd"][0],
            "cost_high": b["cost_usd"][1],
            "known_issues": b.get("known_issues", []),
        })

    plan["total_cost_low"]  = sum(m["cost_low"]  for m in plan["mods"])
    plan["total_cost_high"] = sum(m["cost_high"] for m in plan["mods"])
    plan["phases"] = build_phases(plan["mods"], plan["total_cost_low"])

    return plan


# ── Phase builder ─────────────────────────────────────────────────────────────

def build_phases(mods, total_cost, monthly_budget=1500):
    """
    Build a phased mod plan based on priority and budget.
    Groups mods into monthly phases.
    """
    phases  = []
    current_phase = {"month": 1, "mods": [], "cost": 0}
    sorted_mods = sorted(mods, key=lambda m: m.get("rank", 99))

    for mod in sorted_mods:
        mod_cost = mod.get("cost_low", 0)
        if (current_phase["cost"] + mod_cost > monthly_budget and
                current_phase["mods"]):
            phases.append(current_phase)
            current_phase = {
                "month": len(phases) + 1,
                "mods":  [],
                "cost":  0,
            }
        current_phase["mods"].append(mod["name"])
        current_phase["cost"] += mod_cost

    if current_phase["mods"]:
        phases.append(current_phase)

    return phases


# ── Output formatter ──────────────────────────────────────────────────────────

def format_performance_output(plan):
    lines = []
    gap   = plan["gap"]

    lines.append(f"OPTIMIZATION PLAN — {plan['car']} ({plan['engine']})")
    lines.append(f"GOAL: {plan['goal']}")
    lines.append("=" * 60)
    lines.append(f"Stock power:     {gap['stock_hp']}hp (crank)")
    lines.append(f"Target:          {gap['target_whp']}whp → {gap['target_crank']}hp crank needed")
    lines.append(f"Power gap:       +{gap['hp_gap']}hp")
    lines.append(f"Drivetrain loss: {gap['drivetrain_loss_pct']}% ({plan['drivetrain'].upper()})")

    if plan["warnings"]:
        lines.append("")
        lines.append("⚠  WARNINGS:")
        for w in plan["warnings"]:
            lines.append(f"   {w}")

    lines.append("")
    lines.append("MODIFICATION PLAN:")
    lines.append("-" * 60)

    for mod in sorted(plan["mods"], key=lambda m: m.get("rank", 99)):
        lines.append(f"\n{mod['rank']}. {mod['name']}")
        lines.append(f"   Category:  {mod['category'].replace('_', ' ').title()}")
        lines.append(f"   Gain:      {mod['hp_gain']}")
        lines.append(f"   Location:  {mod['install_location']}")
        lines.append(f"   Cost:      ${mod['cost_low']:,} – ${mod['cost_high']:,}")
        lines.append(f"   Confidence: {mod['confidence_pct']}%")
        if mod.get("known_issues"):
            lines.append(f"   Issues:")
            for issue in mod["known_issues"][:3]:
                lines.append(f"     • {issue}")

    if plan["supporting_mods"]:
        lines.append("")
        lines.append("SUPPORTING HARDWARE REQUIRED:")
        lines.append("-" * 60)
        for s in plan["supporting_mods"][:8]:
            lines.append(f"  • {s}")

    lines.append("")
    lines.append("COST SUMMARY:")
    lines.append("-" * 60)
    lines.append(f"  Minimum:  ${plan['total_cost_low']:,}")
    lines.append(f"  Maximum:  ${plan['total_cost_high']:,}")

    if plan["phases"]:
        lines.append("")
        lines.append("PHASED TIMELINE (at ~$1,500/month):")
        lines.append("-" * 60)
        for phase in plan["phases"]:
            lines.append(f"  Month {phase['month']} (~${phase['cost']:,}):")
            for mod_name in phase["mods"]:
                lines.append(f"    – {mod_name}")

    lines.append("")
    lines.append(f"Overall confidence: {plan['confidence']}%")

    return "\n".join(lines)


def format_efficiency_output(plan):
    lines = []
    lines.append(f"EFFICIENCY OPTIMIZATION — {plan['car']} ({plan['engine']})")
    lines.append(f"GOAL: {plan['goal']}")
    lines.append(f"Estimated fuel economy gain: ~{plan['estimated_mpg_gain_pct']}%")
    lines.append("=" * 60)

    for mod in sorted(plan["mods"], key=lambda m: m.get("rank", 99)):
        lines.append(f"\n{mod['rank']}. {mod['name']}")
        lines.append(f"   Benefit:   {mod['benefit']}")
        lines.append(f"   Location:  {mod['install_location']}")
        lines.append(f"   Cost:      ${mod['cost_low']:,} – ${mod['cost_high']:,}")
        if mod.get("known_issues"):
            for issue in mod["known_issues"][:2]:
                if issue:
                    lines.append(f"   Note:      {issue}")

    lines.append("")
    lines.append(f"TOTAL: ${plan['total_cost_low']:,} – ${plan['total_cost_high']:,}")

    if plan["phases"]:
        lines.append("\nPHASED PLAN:")
        for phase in plan["phases"]:
            lines.append(f"  Month {phase['month']} (~${phase['cost']:,}):")
            for mod_name in phase["mods"]:
                lines.append(f"    – {mod_name}")

    return "\n".join(lines)


def format_handling_output(plan):
    lines = []
    lines.append(f"HANDLING OPTIMIZATION — {plan['car']} ({plan['engine']})")
    lines.append("=" * 60)

    for mod in sorted(plan["mods"], key=lambda m: m.get("rank", 99)):
        lines.append(f"\n{mod['rank']}. {mod['name']}")
        lines.append(f"   Benefit:   {mod['benefit']}")
        lines.append(f"   Location:  {mod['install_location']}")
        lines.append(f"   Cost:      ${mod['cost_low']:,} – ${mod['cost_high']:,}")
        if mod.get("known_issues"):
            for issue in mod["known_issues"][:2]:
                if issue:
                    lines.append(f"   Note:      {issue}")

    lines.append("")
    lines.append(f"TOTAL: ${plan['total_cost_low']:,} – ${plan['total_cost_high']:,}")

    if plan["phases"]:
        lines.append("\nPHASED PLAN:")
        for phase in plan["phases"]:
            lines.append(f"  Month {phase['month']} (~${phase['cost']:,}):")
            for mod_name in phase["mods"]:
                lines.append(f"    – {mod_name}")

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def optimize(query, budget_usd=None):
    """
    Main entry point for the optimization engine.
    Takes a natural language query, returns formatted optimization plan.
    """
    logging.info(f"Optimization query: {query}")

    goal_type, target_value = detect_goal_type(query)
    car_name    = extract_car_from_query(query)
    engine_name = extract_engine_from_query(query)

    if not car_name and not engine_name:
        return (
            "I need a car or engine to optimize for. "
            "Try: 'I want 500whp from my Toyota Supra MK4' "
            "or 'How do I improve fuel economy on my Subaru WRX STI?'"
        )

    specs = load_car_specs(car_name, engine_name)

    if goal_type == "performance":
        if not target_value:
            return (
                f"What's your power target for the {car_name or engine_name}? "
                f"e.g. '500whp' or '400hp'"
            )
        plan   = solve_performance_build(specs, target_value, budget_usd)
        output = format_performance_output(plan)

    elif goal_type == "efficiency":
        plan   = solve_efficiency_build(specs)
        output = format_efficiency_output(plan)

    elif goal_type == "handling":
        plan   = solve_handling_build(specs)
        output = format_handling_output(plan)

    else:
        output = (
            f"I can optimize for: power (e.g. '500whp'), "
            f"fuel efficiency, or handling. "
            f"What's your goal for the {car_name or engine_name}?"
        )

    logging.info(f"Optimization complete: {goal_type} for {car_name or engine_name}")
    return output


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
            "I want 500whp from my Toyota Supra MK4 2JZ-GTE"

    print(f"\nQuery: {query}\n")
    print(optimize(query))
