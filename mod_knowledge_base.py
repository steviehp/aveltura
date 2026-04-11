"""
mod_knowledge_base.py — Vel Optimization Engine Knowledge Base v1

Structured mod data for the physics/optimization engine.
Covers: turbos, superchargers, intercoolers, fuel system, internals,
        suspension, wheels/tyres, exhaust, brakes, ECU, cooling, aero.

Each entry includes:
  - part name and manufacturer
  - performance specs (flow, boost, HP range)
  - compatible engines/platforms
  - install location
  - supporting mods required
  - known issues
  - cost range USD
  - category tags
"""

# ── Turbos ────────────────────────────────────────────────────────────────────

TURBOS = [
    # ── Garrett G-series ──────────────────────────────────────────────────────
    {
        "name": "Garrett G25-550",
        "manufacturer": "Garrett",
        "category": "turbo",
        "max_hp": 550,
        "min_hp": 250,
        "max_flow_cfm": 550,
        "spool_rpm": 2800,
        "compressor_ar": 0.72,
        "turbine_ar": 0.64,
        "compatible_engines": ["2JZ", "RB26", "SR20", "K20", "B18", "EJ20", "EJ25", "FA20"],
        "compatible_platforms": ["universal"],
        "install_location": "exhaust manifold, replaces stock turbo, turbo inlet pipe required",
        "flange": "T25/T28",
        "oil_feed": "banjo fitting, -4AN line from block",
        "oil_return": "-10AN drain to sump",
        "cost_usd": [700, 950],
        "supporting_mods": ["intercooler upgrade", "fuel system upgrade", "ECU tune", "boost controller"],
        "known_issues": [
            "requires custom exhaust manifold on most applications",
            "external wastegate recommended above 400hp",
            "oil feed restrictor required to prevent seal damage"
        ],
        "tags": ["turbo", "forced_induction", "performance", "jdm_compatible"],
    },
    {
        "name": "Garrett G25-660",
        "manufacturer": "Garrett",
        "category": "turbo",
        "max_hp": 660,
        "min_hp": 300,
        "max_flow_cfm": 660,
        "spool_rpm": 3200,
        "compressor_ar": 0.72,
        "turbine_ar": 0.92,
        "compatible_engines": ["2JZ", "RB26", "RB25", "SR20", "EJ25", "EJ257", "1JZ", "VG30"],
        "compatible_platforms": ["universal"],
        "install_location": "exhaust manifold, replaces stock turbos (parallel to single conversion on RB/2JZ)",
        "flange": "T3",
        "oil_feed": "-4AN restrictor fitting from block",
        "oil_return": "-10AN drain to sump",
        "cost_usd": [950, 1250],
        "supporting_mods": ["front mount intercooler", "1000cc+ injectors", "high flow fuel pump", "standalone ECU", "external wastegate", "custom manifold"],
        "known_issues": [
            "lag noticeable below 3000rpm on large displacement engines",
            "custom downpipe required on most platforms",
            "oil restrictor mandatory — seal failure without it",
            "intercooler piping rework required"
        ],
        "tags": ["turbo", "forced_induction", "performance", "single_turbo_conversion"],
    },
    {
        "name": "Garrett GTX3582R",
        "manufacturer": "Garrett",
        "category": "turbo",
        "max_hp": 750,
        "min_hp": 400,
        "max_flow_cfm": 750,
        "spool_rpm": 3800,
        "compressor_ar": 0.82,
        "turbine_ar": 1.01,
        "compatible_engines": ["2JZ", "RB26", "LS", "EJ25", "VR38", "4G63"],
        "compatible_platforms": ["universal"],
        "install_location": "exhaust manifold, T4 flange, requires custom manifold on most builds",
        "flange": "T4",
        "oil_feed": "-4AN restrictor fitting",
        "oil_return": "-10AN drain",
        "cost_usd": [1100, 1500],
        "supporting_mods": ["large front mount intercooler", "1200cc+ injectors", "dual fuel pumps", "standalone ECU", "external wastegate", "custom manifold", "upgraded clutch"],
        "known_issues": [
            "significant lag below 4000rpm — not streetable without anti-lag",
            "requires supporting fuel system rated for 750hp",
            "T4 manifold required — most stock manifolds are T3",
            "heat management critical at this power level"
        ],
        "tags": ["turbo", "forced_induction", "high_power", "track"],
    },
    {
        "name": "Garrett GTX2867R",
        "manufacturer": "Garrett",
        "category": "turbo",
        "max_hp": 450,
        "min_hp": 200,
        "max_flow_cfm": 450,
        "spool_rpm": 2400,
        "compressor_ar": 0.64,
        "turbine_ar": 0.64,
        "compatible_engines": ["K20", "K24", "B18", "B16", "SR20", "4G63", "EJ20", "FA20", "N54", "N55"],
        "compatible_platforms": ["universal"],
        "install_location": "exhaust manifold, replaces stock turbo, T25 or T3 flange depending on application",
        "flange": "T25/T3",
        "oil_feed": "-4AN line",
        "oil_return": "-10AN drain",
        "cost_usd": [750, 1000],
        "supporting_mods": ["intercooler upgrade", "800cc injectors", "fuel pump upgrade", "ECU tune"],
        "known_issues": [
            "may require port matching on some manifolds",
            "boost creep possible without proper wastegate sizing"
        ],
        "tags": ["turbo", "forced_induction", "street_friendly", "responsive"],
    },
    {
        "name": "Garrett G35-900",
        "manufacturer": "Garrett",
        "category": "turbo",
        "max_hp": 900,
        "min_hp": 500,
        "max_flow_cfm": 900,
        "spool_rpm": 4500,
        "compressor_ar": 1.01,
        "turbine_ar": 1.21,
        "compatible_engines": ["2JZ", "RB26", "LS", "Coyote 5.0", "VR38"],
        "compatible_platforms": ["universal"],
        "install_location": "custom manifold required, T4 flange, external wastegate mandatory",
        "flange": "T4",
        "oil_feed": "-4AN restrictor",
        "oil_return": "-10AN drain",
        "cost_usd": [1400, 1900],
        "supporting_mods": ["1600cc+ injectors", "dual bosch 044 pumps", "standalone ECU", "external wastegate 60mm+", "massive front mount intercooler", "upgraded internals recommended"],
        "known_issues": [
            "not street practical without anti-lag or twin scroll setup",
            "heat output extreme — heat shielding mandatory",
            "requires forged internals at full boost"
        ],
        "tags": ["turbo", "forced_induction", "high_power", "race", "1000hp_capable"],
    },

    # ── Precision Turbo ───────────────────────────────────────────────────────
    {
        "name": "Precision 6266 CEA",
        "manufacturer": "Precision Turbo",
        "category": "turbo",
        "max_hp": 625,
        "min_hp": 300,
        "max_flow_cfm": 625,
        "spool_rpm": 3000,
        "compressor_ar": 0.82,
        "turbine_ar": 0.85,
        "compatible_engines": ["2JZ", "RB26", "SR20", "EJ25", "LS", "Coyote"],
        "compatible_platforms": ["universal"],
        "install_location": "exhaust manifold, T3/T4 divided flange",
        "flange": "T3/T4",
        "oil_feed": "-4AN",
        "oil_return": "-10AN",
        "cost_usd": [900, 1200],
        "supporting_mods": ["intercooler", "1000cc injectors", "fuel pump", "tune", "wastegate"],
        "known_issues": [
            "CEA billet wheel — more responsive but pricier than standard",
            "requires proper oil drain angle to prevent pooling"
        ],
        "tags": ["turbo", "forced_induction", "performance", "billet_wheel"],
    },
    {
        "name": "Precision 6870 CEA",
        "manufacturer": "Precision Turbo",
        "category": "turbo",
        "max_hp": 800,
        "min_hp": 450,
        "max_flow_cfm": 800,
        "spool_rpm": 4000,
        "compressor_ar": 1.0,
        "turbine_ar": 1.0,
        "compatible_engines": ["2JZ", "RB26", "LS", "VR38", "Coyote"],
        "compatible_platforms": ["universal"],
        "install_location": "custom T4 manifold, external wastegate required",
        "flange": "T4",
        "oil_feed": "-4AN restrictor",
        "oil_return": "-10AN",
        "cost_usd": [1300, 1700],
        "supporting_mods": ["1200cc+ injectors", "dual fuel pumps", "standalone ECU", "external wastegate", "upgraded clutch/transmission"],
        "known_issues": [
            "large frame — tight fitment in some engine bays",
            "heat management critical",
            "requires forged internals on most engines above 600whp"
        ],
        "tags": ["turbo", "forced_induction", "high_power", "track"],
    },

    # ── BorgWarner ────────────────────────────────────────────────────────────
    {
        "name": "BorgWarner EFR 7163",
        "manufacturer": "BorgWarner",
        "category": "turbo",
        "max_hp": 550,
        "min_hp": 250,
        "max_flow_cfm": 550,
        "spool_rpm": 2600,
        "compressor_ar": 0.71,
        "turbine_ar": 0.85,
        "compatible_engines": ["2JZ", "RB26", "SR20", "EJ25", "K20", "N54"],
        "compatible_platforms": ["universal"],
        "install_location": "exhaust manifold, T3 flange, internal wastegate standard",
        "flange": "T3",
        "oil_feed": "-4AN",
        "oil_return": "-10AN",
        "cost_usd": [1100, 1500],
        "supporting_mods": ["intercooler", "fuel system upgrade", "tune"],
        "known_issues": [
            "internal wastegate limits boost ceiling — external recommended above 400hp",
            "MAP sensor port built in — convenient for boost monitoring"
        ],
        "tags": ["turbo", "forced_induction", "street_friendly", "efr_series"],
    },
    {
        "name": "BorgWarner EFR 8374",
        "manufacturer": "BorgWarner",
        "category": "turbo",
        "max_hp": 750,
        "min_hp": 400,
        "max_flow_cfm": 750,
        "spool_rpm": 3500,
        "compressor_ar": 0.92,
        "turbine_ar": 1.05,
        "compatible_engines": ["2JZ", "RB26", "LS", "Coyote", "EJ25"],
        "compatible_platforms": ["universal"],
        "install_location": "T4 manifold, external wastegate required above 550hp",
        "flange": "T4",
        "oil_feed": "-4AN restrictor",
        "oil_return": "-10AN",
        "cost_usd": [1500, 2000],
        "supporting_mods": ["large FMIC", "1200cc injectors", "dual pumps", "standalone ECU", "external wastegate"],
        "known_issues": [
            "expensive compared to Garrett equivalent",
            "spool noticeably slower than EFR 7163 below 3500rpm",
            "twin scroll housing available — significantly improves spool"
        ],
        "tags": ["turbo", "forced_induction", "high_power", "efr_series"],
    },

    # ── IHI (OEM upgrade) ─────────────────────────────────────────────────────
    {
        "name": "IHI VF52",
        "manufacturer": "IHI",
        "category": "turbo",
        "max_hp": 400,
        "min_hp": 250,
        "max_flow_cfm": 400,
        "spool_rpm": 2200,
        "compatible_engines": ["EJ257", "EJ255", "EJ20"],
        "compatible_platforms": ["Subaru WRX STI", "Subaru WRX", "Subaru Forester XT"],
        "install_location": "direct OEM replacement, mounts to stock manifold, no piping modification needed",
        "flange": "OEM Subaru",
        "oil_feed": "OEM banjo fitting",
        "oil_return": "OEM drain",
        "cost_usd": [400, 650],
        "supporting_mods": ["fuel system tune", "intake upgrade", "intercooler upgrade"],
        "known_issues": [
            "direct fit — easiest upgrade path for EJ platform",
            "boost creep possible on built engines",
            "oil return must be kept clear — EJ sumps prone to oil issues"
        ],
        "tags": ["turbo", "forced_induction", "drop_in", "subaru", "oem_upgrade"],
    },
    {
        "name": "IHI VF39",
        "manufacturer": "IHI",
        "category": "turbo",
        "max_hp": 320,
        "min_hp": 200,
        "max_flow_cfm": 320,
        "spool_rpm": 2000,
        "compatible_engines": ["EJ20", "EJ25"],
        "compatible_platforms": ["Subaru WRX", "Subaru Legacy GT"],
        "install_location": "direct OEM replacement on WRX, stock manifold",
        "flange": "OEM Subaru",
        "oil_feed": "OEM",
        "oil_return": "OEM",
        "cost_usd": [300, 500],
        "supporting_mods": ["tune", "intercooler"],
        "known_issues": ["smaller than VF52 — less top end", "good street manners"],
        "tags": ["turbo", "forced_induction", "drop_in", "subaru"],
    },

    # ── HKS ───────────────────────────────────────────────────────────────────
    {
        "name": "HKS GT2835",
        "manufacturer": "HKS",
        "category": "turbo",
        "max_hp": 450,
        "min_hp": 200,
        "max_flow_cfm": 450,
        "spool_rpm": 2500,
        "compatible_engines": ["SR20DET", "CA18DET", "RB20DET"],
        "compatible_platforms": ["Nissan Silvia S13", "Nissan Silvia S14", "Nissan 180SX"],
        "install_location": "OEM location, replaces stock T28, direct bolt-on with minor modifications",
        "flange": "T28",
        "oil_feed": "-4AN",
        "oil_return": "-10AN",
        "cost_usd": [600, 900],
        "supporting_mods": ["550cc injectors", "fuel pump", "boost controller", "tune"],
        "known_issues": [
            "requires modified oil feed restrictor on SR20",
            "slight piping modification needed for intercooler connection"
        ],
        "tags": ["turbo", "forced_induction", "jdm", "sr20_specific"],
    },
    {
        "name": "HKS GTIII-RS",
        "manufacturer": "HKS",
        "category": "turbo",
        "max_hp": 600,
        "min_hp": 300,
        "max_flow_cfm": 600,
        "spool_rpm": 3200,
        "compatible_engines": ["2JZ-GTE", "1JZ-GTE", "RB26DETT", "RB25DET"],
        "compatible_platforms": ["Toyota Supra A80", "Toyota Aristo", "Nissan Skyline R32/R33/R34"],
        "install_location": "exhaust manifold, replaces stock twin turbos with single conversion kit, driver side of engine bay",
        "flange": "T3",
        "oil_feed": "-4AN restrictor",
        "oil_return": "-10AN",
        "cost_usd": [1200, 1600],
        "supporting_mods": ["single turbo conversion manifold", "FMIC", "1000cc injectors", "E85 capable fuel system", "standalone ECU", "external wastegate"],
        "known_issues": [
            "single conversion requires manifold and wastegate purchase separately",
            "2JZ sequential system must be deleted",
            "boost response slower than stock sequential below 3500rpm"
        ],
        "tags": ["turbo", "forced_induction", "jdm", "single_conversion", "high_power"],
    },
]

# ── Superchargers ─────────────────────────────────────────────────────────────

SUPERCHARGERS = [
    {
        "name": "Magnuson TVS2300",
        "manufacturer": "Magnuson",
        "category": "supercharger",
        "type": "Roots/TVS",
        "max_hp_gain": 200,
        "boost_psi": 8,
        "compatible_engines": ["LS3", "LS7", "LT1", "LT4"],
        "compatible_platforms": ["Chevrolet Corvette C6/C7", "Chevrolet Camaro SS/Z28", "GM trucks"],
        "install_location": "top of engine, replaces intake manifold, drives from crank pulley via belt",
        "cost_usd": [2800, 4500],
        "supporting_mods": ["intercooler (built in on most kits)", "fuel injector upgrade", "tune", "heat exchanger"],
        "known_issues": [
            "heat soak on track use — heat exchanger upgrade recommended",
            "belt slip above 650hp — upgraded belt tensioner needed",
            "requires full tune for safe operation"
        ],
        "tags": ["supercharger", "forced_induction", "ls_platform", "street_friendly"],
    },
    {
        "name": "Whipple W175FF 2.9L",
        "manufacturer": "Whipple",
        "category": "supercharger",
        "type": "Twin Screw",
        "max_hp_gain": 350,
        "boost_psi": 14,
        "compatible_engines": ["Coyote 5.0", "GT350 Voodoo 5.2", "Predator 5.2"],
        "compatible_platforms": ["Ford Mustang GT S550", "Ford Mustang GT350 S550", "Ford F-150 5.0"],
        "install_location": "top mount, replaces intake manifold, drives from crank via 8-rib belt",
        "cost_usd": [3500, 5500],
        "supporting_mods": ["60lb+ injectors", "flex fuel kit", "fuel pump booster", "standalone or piggyback tune", "heat exchanger"],
        "known_issues": [
            "requires tune before first startup — lean condition without it",
            "stock fuel system maxes around 650hp",
            "belt drive system loud at idle — normal characteristic"
        ],
        "tags": ["supercharger", "forced_induction", "mustang", "coyote", "high_power"],
    },
    {
        "name": "Roush Phase 3 Supercharger",
        "manufacturer": "Roush",
        "category": "supercharger",
        "type": "Positive Displacement",
        "max_hp_gain": 190,
        "boost_psi": 9,
        "compatible_engines": ["Coyote 5.0"],
        "compatible_platforms": ["Ford Mustang GT 2015-2023"],
        "install_location": "top mount, direct bolt-on intake manifold replacement",
        "cost_usd": [2200, 3200],
        "supporting_mods": ["tune", "cold air intake", "upgraded fuel injectors recommended above 600hp"],
        "known_issues": [
            "one of the easier blower installs on Coyote",
            "power limited compared to Whipple at high boost",
            "tune critical — do not run without"
        ],
        "tags": ["supercharger", "forced_induction", "mustang", "coyote", "street_friendly"],
    },
    {
        "name": "Kraftwerks C30-94 Rotrex",
        "manufacturer": "Kraftwerks",
        "category": "supercharger",
        "type": "Centrifugal",
        "max_hp_gain": 150,
        "boost_psi": 8,
        "compatible_engines": ["K20", "K24", "F20C", "F22C"],
        "compatible_platforms": ["Honda Civic Si", "Honda S2000", "Acura RSX Type-S", "Honda CR-Z"],
        "install_location": "front of engine, belt driven from crank, mounts to existing brackets",
        "cost_usd": [2500, 3500],
        "supporting_mods": ["tune (Hondata or AEM)", "upgraded injectors", "fuel pump", "oil cooler"],
        "known_issues": [
            "centrifugal design means boost builds with RPM — low RPM response unchanged",
            "oil cooled unit — requires oil feed and return lines",
            "intercooler recommended above 7psi"
        ],
        "tags": ["supercharger", "forced_induction", "honda", "k_series", "centrifugal"],
    },
    {
        "name": "Jackson Racing C38 Supercharger",
        "manufacturer": "Jackson Racing",
        "category": "supercharger",
        "type": "Roots",
        "max_hp_gain": 100,
        "boost_psi": 6,
        "compatible_engines": ["K20", "K24"],
        "compatible_platforms": ["Honda Civic 2006-2015", "Honda CR-V", "Acura RSX"],
        "install_location": "top mount, replaces intake manifold directly",
        "cost_usd": [3200, 4200],
        "supporting_mods": ["tune", "injector upgrade recommended"],
        "known_issues": [
            "heat soak on sustained boost",
            "OEM quality fitment — very clean install"
        ],
        "tags": ["supercharger", "forced_induction", "honda", "k_series", "top_mount"],
    },
]

# ── Intercoolers ──────────────────────────────────────────────────────────────

INTERCOOLERS = [
    {
        "name": "Mishimoto Universal Front Mount Intercooler",
        "manufacturer": "Mishimoto",
        "category": "intercooler",
        "type": "FMIC",
        "core_size_mm": "600x300x76",
        "efficiency_pct": 85,
        "max_hp": 600,
        "compatible_engines": ["universal"],
        "compatible_platforms": ["universal — requires custom piping"],
        "install_location": "front of engine bay behind bumper, between radiator and bumper support",
        "cost_usd": [250, 450],
        "supporting_mods": ["custom intercooler piping", "couplers and clamps", "BOV relocation possibly"],
        "known_issues": [
            "universal fit requires custom pipe fabrication",
            "may restrict airflow to radiator if oversized — watch coolant temps"
        ],
        "tags": ["intercooler", "fmic", "universal", "cooling"],
    },
    {
        "name": "GReddy Front Mount Intercooler Kit — Nissan Silvia S14",
        "manufacturer": "GReddy",
        "category": "intercooler",
        "type": "FMIC",
        "core_size_mm": "550x180x65",
        "efficiency_pct": 83,
        "max_hp": 450,
        "compatible_engines": ["SR20DET"],
        "compatible_platforms": ["Nissan Silvia S14", "Nissan 180SX"],
        "install_location": "front mount, replaces OEM SMIC, full bolt-on kit with piping",
        "cost_usd": [500, 800],
        "supporting_mods": ["none — full kit includes piping"],
        "known_issues": [
            "slight drop in throttle response vs side mount",
            "full replacement — cleaner than SMIC upgrade"
        ],
        "tags": ["intercooler", "fmic", "nissan", "sr20", "bolt_on_kit"],
    },
    {
        "name": "Perrin FMIC Kit — Subaru WRX/STI",
        "manufacturer": "Perrin",
        "category": "intercooler",
        "type": "FMIC",
        "core_size_mm": "560x200x65",
        "efficiency_pct": 86,
        "max_hp": 500,
        "compatible_engines": ["EJ255", "EJ257", "FA20DIT"],
        "compatible_platforms": ["Subaru WRX 2008-2021", "Subaru STI 2008-2021"],
        "install_location": "front mount, replaces top mount OEM intercooler, full kit with piping and couplers",
        "cost_usd": [700, 1100],
        "supporting_mods": ["tune recommended after install"],
        "known_issues": [
            "top mount to front mount conversion — slight spool delay",
            "may require bumper modification on some years",
            "thermal cycling can loosen coupler clamps — check after 500mi"
        ],
        "tags": ["intercooler", "fmic", "subaru", "wrx", "sti", "bolt_on_kit"],
    },
    {
        "name": "Treadstone TR8L Universal FMIC",
        "manufacturer": "Treadstone",
        "category": "intercooler",
        "type": "FMIC",
        "core_size_mm": "700x300x100",
        "efficiency_pct": 90,
        "max_hp": 900,
        "compatible_engines": ["universal"],
        "compatible_platforms": ["universal — custom piping required"],
        "install_location": "front mount, maximum size for most engine bays, custom piping required",
        "cost_usd": [350, 600],
        "supporting_mods": ["custom piping", "couplers", "may need bumper modification"],
        "known_issues": [
            "very large — fitment in smaller engine bays difficult",
            "custom piping mandatory — no bolt-on option",
            "excellent thermal performance — worth the effort on high power builds"
        ],
        "tags": ["intercooler", "fmic", "universal", "high_power", "large_core"],
    },
    {
        "name": "HKS R-type Intercooler — Toyota Supra A80",
        "manufacturer": "HKS",
        "category": "intercooler",
        "type": "FMIC",
        "core_size_mm": "600x250x76",
        "efficiency_pct": 88,
        "max_hp": 700,
        "compatible_engines": ["2JZ-GTE", "2JZ-GE"],
        "compatible_platforms": ["Toyota Supra A80 1993-1998"],
        "install_location": "front mount, replaces OEM sequential turbo intercooler, includes all piping",
        "cost_usd": [900, 1400],
        "supporting_mods": ["none — full kit"],
        "known_issues": [
            "designed for single turbo conversion",
            "OEM sequential system piping will not connect — single turbo required"
        ],
        "tags": ["intercooler", "fmic", "toyota", "2jz", "supra", "single_turbo"],
    },
]

# ── Fuel System ───────────────────────────────────────────────────────────────

INJECTORS = [
    {
        "name": "Injector Dynamics ID725",
        "manufacturer": "Injector Dynamics",
        "category": "injector",
        "flow_cc_min": 725,
        "max_hp_support": 500,
        "fuel_type": ["pump gas", "E85"],
        "compatible_engines": ["K20", "K24", "B18", "F20C", "SR20", "EJ20", "EJ25"],
        "install_location": "fuel rail, direct replacement of OEM injectors",
        "cost_usd": [550, 750],
        "supporting_mods": ["fuel pressure regulator check", "tune mandatory"],
        "known_issues": ["ID injectors require characterization data loaded into ECU for accurate fueling"],
        "tags": ["fuel", "injector", "high_flow"],
    },
    {
        "name": "Injector Dynamics ID1050x",
        "manufacturer": "Injector Dynamics",
        "category": "injector",
        "flow_cc_min": 1050,
        "max_hp_support": 750,
        "fuel_type": ["pump gas", "E85", "methanol"],
        "compatible_engines": ["2JZ", "RB26", "SR20", "EJ25", "K20", "LS", "Coyote"],
        "install_location": "fuel rail, may require adapter clips on some applications",
        "cost_usd": [750, 950],
        "supporting_mods": ["upgraded fuel pump", "fuel pressure regulator", "return style fuel system", "standalone ECU"],
        "known_issues": [
            "very large — idle quality may suffer on small displacement engines",
            "requires proper characterization data in ECU",
            "returnless fuel systems need conversion to return style at this flow rate"
        ],
        "tags": ["fuel", "injector", "high_flow", "e85_capable"],
    },
    {
        "name": "Bosch EV14 1000cc",
        "manufacturer": "Bosch",
        "category": "injector",
        "flow_cc_min": 1000,
        "max_hp_support": 700,
        "fuel_type": ["pump gas", "E85"],
        "compatible_engines": ["2JZ", "RB26", "SR20", "EJ25", "VR38", "universal"],
        "install_location": "fuel rail, O-ring seal, may require adapters",
        "cost_usd": [350, 550],
        "supporting_mods": ["fuel pump upgrade", "tune"],
        "known_issues": ["good budget option vs ID injectors", "less characterization data available"],
        "tags": ["fuel", "injector", "high_flow", "budget_friendly"],
    },
]

FUEL_PUMPS = [
    {
        "name": "Walbro 450 (F90000274)",
        "manufacturer": "Walbro",
        "category": "fuel_pump",
        "flow_lph": 450,
        "max_hp_support": 650,
        "fuel_type": ["pump gas", "E85"],
        "install_location": "in-tank, replaces OEM pump module, fits most OEM baskets",
        "cost_usd": [80, 130],
        "supporting_mods": ["fuel pump wiring harness upgrade on high current draw", "tune"],
        "known_issues": [
            "direct drop-in on most applications",
            "E85 compatible — verify O-rings are alcohol resistant",
            "may whine at idle — normal characteristic"
        ],
        "tags": ["fuel", "pump", "in_tank", "e85_capable"],
    },
    {
        "name": "Bosch 044 External Fuel Pump",
        "manufacturer": "Bosch",
        "category": "fuel_pump",
        "flow_lph": 300,
        "max_hp_support": 700,
        "fuel_type": ["pump gas", "E85", "race fuel"],
        "install_location": "external inline, typically mounted on chassis rail or subframe near fuel tank",
        "cost_usd": [150, 220],
        "supporting_mods": ["fuel filter before pump", "braided fuel line", "relay and wiring", "check valve"],
        "known_issues": [
            "loud — external mount amplifies pump noise into cabin",
            "runs hot — needs adequate airflow for cooling",
            "often run in pairs for 1000hp+ builds"
        ],
        "tags": ["fuel", "pump", "external", "high_flow", "race"],
    },
    {
        "name": "DeatschWerks DW300C",
        "manufacturer": "DeatschWerks",
        "category": "fuel_pump",
        "flow_lph": 340,
        "max_hp_support": 500,
        "fuel_type": ["pump gas", "E85"],
        "install_location": "in-tank drop-in replacement, fits OEM basket",
        "cost_usd": [120, 180],
        "supporting_mods": ["tune"],
        "known_issues": [
            "excellent E85 compatibility",
            "quiet compared to Walbro — better daily driver option",
            "DeatschWerks provides application-specific fitment kits"
        ],
        "tags": ["fuel", "pump", "in_tank", "e85_capable", "street_friendly"],
    },
]

# ── Engine Internals ──────────────────────────────────────────────────────────

PISTONS = [
    {
        "name": "Wiseco Forged Pistons — 2JZ",
        "manufacturer": "Wiseco",
        "category": "piston",
        "material": "forged 2618 aluminum",
        "max_hp_support": 1000,
        "compatible_engines": ["2JZ-GTE", "2JZ-GE"],
        "bore_sizes_available": [86.5, 87.0, 87.5, 88.0],
        "compression_ratio_options": [8.5, 9.0, 9.5],
        "install_location": "engine block, replace OEM cast pistons, requires engine teardown",
        "cost_usd": [700, 1100],
        "supporting_mods": ["forged connecting rods", "ACL or King bearings", "engine rebuild gasket set", "head studs", "machine shop work"],
        "known_issues": [
            "engine must be fully disassembled",
            "bore size must be matched to pistons — machine shop required",
            "piston to wall clearance critical — too tight causes seizing, too loose causes blow-by",
            "break-in procedure mandatory"
        ],
        "tags": ["internals", "piston", "forged", "2jz", "high_power"],
    },
    {
        "name": "CP Pistons Forged — EJ25",
        "manufacturer": "CP Pistons",
        "category": "piston",
        "material": "forged 2618 aluminum",
        "max_hp_support": 600,
        "compatible_engines": ["EJ255", "EJ257"],
        "bore_sizes_available": [99.5, 100.0, 100.5],
        "compression_ratio_options": [8.2, 8.5, 9.0],
        "install_location": "engine block, replace OEM pistons",
        "cost_usd": [600, 900],
        "supporting_mods": ["EJ rods (stock rods good to 450whp)", "bearings", "gaskets", "head studs ARP", "machine shop"],
        "known_issues": [
            "EJ block has ring land issues above 400whp on cast pistons",
            "piston to head clearance critical on EJ — measure carefully",
            "ringland failure common above 350whp on stock pistons"
        ],
        "tags": ["internals", "piston", "forged", "subaru", "ej"],
    },
    {
        "name": "JE Pistons Forged — LS",
        "manufacturer": "JE Pistons",
        "category": "piston",
        "material": "forged 2618 aluminum",
        "max_hp_support": 1200,
        "compatible_engines": ["LS1", "LS2", "LS3", "LS6", "LS7"],
        "bore_sizes_available": [101.6, 102.0, 102.5, 103.0, 104.0],
        "compression_ratio_options": [9.0, 10.0, 11.0, 12.0],
        "install_location": "engine block",
        "cost_usd": [700, 1200],
        "supporting_mods": ["Manley or Eagle rods", "King or Clevite bearings", "LS gasket kit", "ARP head studs"],
        "known_issues": [
            "LS platform very tolerant — stock block handles 700-800hp reliably",
            "skirt clearance must be correct for chosen application"
        ],
        "tags": ["internals", "piston", "forged", "ls_platform", "high_power"],
    },
]

CONNECTING_RODS = [
    {
        "name": "Manley H-beam Rods — 2JZ",
        "manufacturer": "Manley",
        "category": "connecting_rod",
        "material": "4340 chromoly steel",
        "max_hp_support": 1000,
        "compatible_engines": ["2JZ-GTE", "2JZ-GE"],
        "install_location": "engine block, replace OEM rods",
        "cost_usd": [600, 900],
        "supporting_mods": ["ARP rod bolts", "forged pistons", "bearings"],
        "known_issues": [
            "H-beam design better for high boost, I-beam better for high RPM",
            "ARP2000 rod bolts mandatory — stock bolts not reusable"
        ],
        "tags": ["internals", "connecting_rod", "2jz", "forged"],
    },
    {
        "name": "Brian Crower Rods — EJ25",
        "manufacturer": "Brian Crower",
        "category": "connecting_rod",
        "material": "4340 chromoly steel H-beam",
        "max_hp_support": 700,
        "compatible_engines": ["EJ255", "EJ257"],
        "install_location": "engine block",
        "cost_usd": [550, 800],
        "supporting_mods": ["forged pistons", "ARP head studs", "bearings"],
        "known_issues": [
            "stock EJ rods acceptable to 450whp — upgrade when going further",
            "measure rod length carefully — EJ is sensitive to rod ratio changes"
        ],
        "tags": ["internals", "connecting_rod", "subaru", "ej", "forged"],
    },
]

HEAD_STUDS = [
    {
        "name": "ARP Head Studs — 2JZ",
        "manufacturer": "ARP",
        "category": "head_stud",
        "material": "8740 chromoly steel",
        "max_hp_support": 1500,
        "compatible_engines": ["2JZ-GTE", "2JZ-GE"],
        "install_location": "cylinder head, replace OEM head bolts",
        "cost_usd": [200, 300],
        "supporting_mods": ["MLS head gasket", "proper torque sequence"],
        "known_issues": [
            "mandatory above 500hp — OEM bolts stretch and cause head lift",
            "torque to yield OEM bolts should never be reused",
            "requires proper torque wrench and sequence"
        ],
        "tags": ["internals", "head_stud", "2jz", "essential"],
    },
    {
        "name": "ARP Head Studs — EJ25",
        "manufacturer": "ARP",
        "category": "head_stud",
        "material": "8740 chromoly steel",
        "max_hp_support": 800,
        "compatible_engines": ["EJ255", "EJ257", "EJ20"],
        "install_location": "cylinder head",
        "cost_usd": [180, 280],
        "supporting_mods": ["Cometic MLS head gasket", "fresh coolant system"],
        "known_issues": [
            "EJ engines notorious for head gasket failure — studs mandatory on any boost build",
            "fire ring head gasket + studs = solved problem",
            "proper cooling system maintenance critical after install"
        ],
        "tags": ["internals", "head_stud", "subaru", "ej", "essential"],
    },
    {
        "name": "ARP Head Studs — LS",
        "manufacturer": "ARP",
        "category": "head_stud",
        "material": "8740 chromoly steel",
        "max_hp_support": 1500,
        "compatible_engines": ["LS1", "LS2", "LS3", "LS6", "LS7"],
        "install_location": "cylinder head",
        "cost_usd": [160, 260],
        "supporting_mods": ["MLS head gasket recommended above 600hp"],
        "known_issues": [
            "LS OEM head bolts surprisingly good — studs needed above 700hp",
        ],
        "tags": ["internals", "head_stud", "ls_platform"],
    },
]

# ── Suspension ────────────────────────────────────────────────────────────────

COILOVERS = [
    {
        "name": "BC Racing BR Series Coilovers",
        "manufacturer": "BC Racing",
        "category": "coilover",
        "adjustability": "height adjustable, 30-way damping",
        "spring_rate_front_kgmm": 8,
        "spring_rate_rear_kgmm": 6,
        "compatible_platforms": ["universal — application specific"],
        "install_location": "all 4 corners, replace OEM struts and springs",
        "cost_usd": [700, 1100],
        "supporting_mods": ["alignment after install", "camber bolts or plates if going very low"],
        "known_issues": [
            "budget-friendly but spring rates may not suit track use",
            "30-way adjustment gives good street/track balance",
            "lower than 25mm from stock may cause clearance issues",
            "alignment critical after any height adjustment"
        ],
        "tags": ["suspension", "coilover", "street_track", "height_adjustable"],
    },
    {
        "name": "KW Variant 3 Coilovers",
        "manufacturer": "KW",
        "category": "coilover",
        "adjustability": "height adjustable, independent rebound and compression adjustment",
        "spring_rate_front_kgmm": 10,
        "spring_rate_rear_kgmm": 8,
        "compatible_platforms": ["BMW E46", "BMW E90/E92", "VW Golf MK5/MK6", "Audi A3/S3", "Porsche 996/997"],
        "install_location": "all 4 corners",
        "cost_usd": [1800, 2600],
        "supporting_mods": ["alignment", "camber plates (included on some kits)"],
        "known_issues": [
            "expensive but excellent quality",
            "inox stainless hardware — corrosion resistant",
            "independent adjustment allows proper track setup"
        ],
        "tags": ["suspension", "coilover", "premium", "track_capable", "european"],
    },
    {
        "name": "Tein Flex Z Coilovers",
        "manufacturer": "Tein",
        "category": "coilover",
        "adjustability": "height adjustable, 16-way damping",
        "spring_rate_front_kgmm": 7,
        "spring_rate_rear_kgmm": 5,
        "compatible_platforms": ["Toyota, Honda, Nissan, Subaru — application specific"],
        "install_location": "all 4 corners",
        "cost_usd": [550, 850],
        "supporting_mods": ["alignment", "EDFC optional (electronic damping from cabin)"],
        "known_issues": [
            "soft spring rates — better for street comfort than track",
            "EDFC controller available for cabin-adjustable damping",
            "good daily driver option"
        ],
        "tags": ["suspension", "coilover", "street", "comfort_biased", "jdm"],
    },
    {
        "name": "Öhlins Road & Track",
        "manufacturer": "Öhlins",
        "category": "coilover",
        "adjustability": "height adjustable, continuous damping adjustment",
        "spring_rate_front_kgmm": 12,
        "spring_rate_rear_kgmm": 10,
        "compatible_platforms": ["BMW M3 E46/E90/F80", "Porsche 911 996/997/991", "Nissan GT-R R35", "Toyota GR86"],
        "install_location": "all 4 corners",
        "cost_usd": [3000, 5000],
        "supporting_mods": ["camber plates", "alignment"],
        "known_issues": [
            "best in class performance — price reflects it",
            "requires proper setup for optimal performance",
            "Swedish engineering — very well built"
        ],
        "tags": ["suspension", "coilover", "premium", "track", "race_grade"],
    },
]

SWAY_BARS = [
    {
        "name": "Whiteline Front and Rear Sway Bar Kit",
        "manufacturer": "Whiteline",
        "category": "sway_bar",
        "adjustability": "multiple hole adjustment for stiffness",
        "compatible_platforms": ["Subaru WRX/STI", "Toyota GR86/BRZ", "Nissan 350Z/370Z"],
        "install_location": "front: replaces OEM front bar at front subframe. Rear: replaces OEM rear bar at rear subframe",
        "cost_usd": [300, 600],
        "supporting_mods": ["end links", "alignment check"],
        "known_issues": [
            "stiffer rear bar can induce oversteer — tune carefully",
            "excellent handling improvement for street and track",
            "polyurethane bushings included — grease required"
        ],
        "tags": ["suspension", "sway_bar", "handling", "bolt_on"],
    },
]

# ── Wheels & Tyres ────────────────────────────────────────────────────────────

WHEELS = [
    {
        "name": "Enkei RPF1",
        "manufacturer": "Enkei",
        "category": "wheel",
        "material": "flow formed aluminum",
        "weight_kg": 6.8,
        "sizes_available": ["15x7", "15x8", "16x7", "17x8", "17x9", "18x9.5"],
        "compatible_platforms": ["universal"],
        "cost_usd": [180, 280],
        "notes": "lightweight, strong, excellent track choice, classic look",
        "tags": ["wheel", "lightweight", "track", "universal"],
    },
    {
        "name": "Rays Volk Racing TE37",
        "manufacturer": "Rays Engineering",
        "category": "wheel",
        "material": "forged aluminum 6061-T6",
        "weight_kg": 6.2,
        "sizes_available": ["15x8", "16x7", "17x8", "17x9", "18x9.5", "18x10"],
        "compatible_platforms": ["universal"],
        "cost_usd": [500, 800],
        "notes": "iconic forged wheel, extremely strong, minimal unsprung weight",
        "tags": ["wheel", "forged", "lightweight", "premium", "iconic"],
    },
    {
        "name": "BBS CH-R",
        "manufacturer": "BBS",
        "category": "wheel",
        "material": "flow formed aluminum",
        "weight_kg": 8.5,
        "sizes_available": ["18x8", "18x8.5", "19x8.5", "19x9", "20x9"],
        "compatible_platforms": ["BMW", "Mercedes", "Audi", "Porsche"],
        "cost_usd": [400, 700],
        "notes": "premium European fitment, OEM supplier to BMW M and Porsche",
        "tags": ["wheel", "premium", "european", "oem_supplier"],
    },
]

TYRES = [
    {
        "name": "Michelin Pilot Sport 4S",
        "manufacturer": "Michelin",
        "category": "tyre",
        "type": "ultra high performance street",
        "rolling_resistance": "low",
        "wet_grip": "A",
        "dry_grip": "excellent",
        "treadwear": 300,
        "sizes_available": ["225/40R18", "245/35R19", "265/35R19", "305/30R20"],
        "cost_usd_per_tyre": [180, 320],
        "notes": "best street tyre for performance — benchmark in class",
        "tags": ["tyre", "performance", "street", "wet_capable"],
    },
    {
        "name": "Michelin Pilot Sport Cup 2",
        "manufacturer": "Michelin",
        "category": "tyre",
        "type": "semi-slick",
        "rolling_resistance": "moderate",
        "wet_grip": "C",
        "dry_grip": "exceptional",
        "treadwear": 180,
        "sizes_available": ["245/35R19", "265/35R19", "305/30R20", "325/30R20"],
        "cost_usd_per_tyre": [280, 450],
        "notes": "track day and performance driving — poor in wet/cold",
        "tags": ["tyre", "semi_slick", "track", "dry_only"],
    },
    {
        "name": "Continental EcoContact 6",
        "manufacturer": "Continental",
        "category": "tyre",
        "type": "eco/touring",
        "rolling_resistance": "very low",
        "wet_grip": "A",
        "dry_grip": "good",
        "treadwear": 600,
        "sizes_available": ["195/65R15", "205/55R16", "225/45R17", "235/45R18"],
        "cost_usd_per_tyre": [100, 160],
        "notes": "low rolling resistance — fuel efficiency focused",
        "tags": ["tyre", "eco", "fuel_efficiency", "long_life"],
    },
    {
        "name": "Yokohama Advan A052",
        "manufacturer": "Yokohama",
        "category": "tyre",
        "type": "semi-slick",
        "rolling_resistance": "moderate",
        "wet_grip": "C",
        "dry_grip": "exceptional",
        "treadwear": 200,
        "sizes_available": ["225/45R17", "245/40R18", "265/35R18", "275/35R19"],
        "cost_usd_per_tyre": [200, 350],
        "notes": "aggressive compound — excellent autocross and track day tyre",
        "tags": ["tyre", "semi_slick", "track", "autocross"],
    },
]

# ── ECU / Tune ────────────────────────────────────────────────────────────────

ECU_SYSTEMS = [
    {
        "name": "Link G4X Plugin ECU",
        "manufacturer": "Link",
        "category": "ecu",
        "type": "standalone",
        "max_injectors": 8,
        "max_ignition_outputs": 8,
        "flex_fuel_capable": True,
        "launch_control": True,
        "traction_control": True,
        "compatible_platforms": ["Toyota Supra A80", "Nissan Skyline R32/R33/R34", "Nissan Silvia S13/S14/S15", "Subaru WRX/STI", "Honda Civic/Integra"],
        "install_location": "OEM ECU location, plugs directly into factory wiring harness",
        "cost_usd": [1200, 2000],
        "supporting_mods": ["wideband O2 sensor", "map sensor upgrade for high boost", "tune by qualified tuner"],
        "known_issues": [
            "plug-in versions available for most common JDM platforms",
            "PCLink software free — excellent support",
            "requires experienced tuner for optimal results"
        ],
        "tags": ["ecu", "standalone", "plug_in", "jdm", "flex_fuel"],
    },
    {
        "name": "Haltech Elite 2500",
        "manufacturer": "Haltech",
        "category": "ecu",
        "type": "standalone",
        "max_injectors": 8,
        "max_ignition_outputs": 8,
        "flex_fuel_capable": True,
        "launch_control": True,
        "traction_control": True,
        "compatible_platforms": ["universal — requires wiring"],
        "install_location": "custom mount, full wire-in harness required",
        "cost_usd": [2000, 3200],
        "supporting_mods": ["wiring harness build or kit", "wideband O2", "tune"],
        "known_issues": [
            "wire-in only — requires full harness build or pre-made kit",
            "extremely capable — used in professional motorsport",
            "ESP software good but learning curve steeper than Link"
        ],
        "tags": ["ecu", "standalone", "wire_in", "professional", "universal"],
    },
    {
        "name": "AEM Infinity 6",
        "manufacturer": "AEM",
        "category": "ecu",
        "type": "standalone",
        "max_injectors": 6,
        "max_ignition_outputs": 6,
        "flex_fuel_capable": True,
        "launch_control": True,
        "traction_control": False,
        "compatible_platforms": ["universal"],
        "install_location": "custom mount, wire-in",
        "cost_usd": [1500, 2500],
        "supporting_mods": ["wideband O2", "tune"],
        "known_issues": [
            "good for 4 and 6 cylinder applications",
            "AEMtuner software decent",
            "no traction control — limitation vs Haltech/Link"
        ],
        "tags": ["ecu", "standalone", "wire_in", "4_6_cylinder"],
    },
    {
        "name": "Hondata S300",
        "manufacturer": "Hondata",
        "category": "ecu",
        "type": "piggyback/reflash",
        "flex_fuel_capable": True,
        "launch_control": True,
        "traction_control": False,
        "compatible_platforms": ["Honda Civic EG/EK", "Honda Integra DC2", "Honda CRX"],
        "install_location": "installs inside OEM ECU housing, requires OEM ECU modification",
        "cost_usd": [500, 800],
        "supporting_mods": ["wideband O2", "tune by Hondata certified tuner"],
        "known_issues": [
            "OBD1 Honda only",
            "excellent Honda platform support",
            "KPro available for OBD2 Honda platforms"
        ],
        "tags": ["ecu", "honda", "obd1", "piggyback"],
    },
    {
        "name": "EcuTek RaceROM — Subaru",
        "manufacturer": "EcuTek",
        "category": "ecu",
        "type": "reflash",
        "flex_fuel_capable": True,
        "launch_control": True,
        "traction_control": True,
        "compatible_platforms": ["Subaru WRX 2008-2021", "Subaru STI 2008-2021", "Subaru BRZ"],
        "install_location": "OEM ECU, software flash via OBD2 port",
        "cost_usd": [600, 1200],
        "supporting_mods": ["wideband O2", "AccessPort compatible"],
        "known_issues": [
            "requires dealer or tuner with EcuTek license",
            "excellent Subaru platform support",
            "RaceROM features unlock advanced functionality"
        ],
        "tags": ["ecu", "reflash", "subaru", "wrx", "sti"],
    },
]

# ── Exhaust ───────────────────────────────────────────────────────────────────

EXHAUSTS = [
    {
        "name": "HKS Hi-Power Spec-L Cat-Back — Toyota Supra A80",
        "manufacturer": "HKS",
        "category": "exhaust",
        "type": "cat-back",
        "pipe_diameter_mm": 80,
        "hp_gain_estimate": 15,
        "sound_level": "moderate",
        "compatible_engines": ["2JZ-GTE", "2JZ-GE"],
        "compatible_platforms": ["Toyota Supra A80 1993-1998"],
        "install_location": "replaces OEM cat-back from catalytic converter back, uses OEM mounting points",
        "cost_usd": [800, 1200],
        "supporting_mods": ["none — bolt-on"],
        "known_issues": [
            "direct bolt-on",
            "resonated tip reduces drone",
            "available in multiple tip styles"
        ],
        "tags": ["exhaust", "cat_back", "toyota", "2jz", "supra", "bolt_on"],
    },
    {
        "name": "Borla ATAK Cat-Back — Ford Mustang S550",
        "manufacturer": "Borla",
        "category": "exhaust",
        "type": "cat-back",
        "pipe_diameter_mm": 76,
        "hp_gain_estimate": 20,
        "sound_level": "aggressive",
        "compatible_engines": ["Coyote 5.0", "Voodoo 5.2"],
        "compatible_platforms": ["Ford Mustang GT 2015-2023", "Ford Mustang GT350 2015-2020"],
        "install_location": "replaces OEM cat-back, uses OEM hangers",
        "cost_usd": [900, 1400],
        "supporting_mods": ["none — direct bolt-on"],
        "known_issues": [
            "ATAK is louder than S-Type and Touring variants",
            "check local noise ordinances — may fail inspection in some areas"
        ],
        "tags": ["exhaust", "cat_back", "ford", "mustang", "coyote", "aggressive"],
    },
    {
        "name": "Tomei Expreme Ti Titanium Cat-Back — Subaru",
        "manufacturer": "Tomei",
        "category": "exhaust",
        "type": "cat-back",
        "pipe_diameter_mm": 80,
        "hp_gain_estimate": 18,
        "sound_level": "aggressive",
        "compatible_engines": ["EJ255", "EJ257"],
        "compatible_platforms": ["Subaru WRX 2008-2014", "Subaru STI 2008-2021"],
        "install_location": "cat-back, uses OEM mounting points",
        "cost_usd": [900, 1300],
        "supporting_mods": ["none — bolt-on"],
        "known_issues": [
            "titanium construction — very light",
            "pops and crackles on decel with proper tune",
            "iconic Subaru sound"
        ],
        "tags": ["exhaust", "cat_back", "subaru", "titanium", "wrx", "sti"],
    },
    {
        "name": "Thermal R&D Test Pipe — Nissan Skyline R34",
        "manufacturer": "Thermal R&D",
        "category": "exhaust",
        "type": "downpipe",
        "pipe_diameter_mm": 90,
        "hp_gain_estimate": 25,
        "sound_level": "loud",
        "compatible_engines": ["RB26DETT"],
        "compatible_platforms": ["Nissan Skyline R34 GT-R"],
        "install_location": "replaces OEM catalytic converter and downpipe, turbo outlet connection",
        "cost_usd": [400, 700],
        "supporting_mods": ["tune recommended", "cat-back system"],
        "known_issues": [
            "test pipe = no catalyst — not street legal in most jurisdictions",
            "significant power gain over OEM",
            "requires tune for best results"
        ],
        "tags": ["exhaust", "downpipe", "test_pipe", "nissan", "rb26", "track"],
    },
]

# ── Brakes ────────────────────────────────────────────────────────────────────

BRAKES = [
    {
        "name": "Brembo GT 6-Piston Front Big Brake Kit",
        "manufacturer": "Brembo",
        "category": "brake",
        "type": "big brake kit",
        "piston_count_front": 6,
        "rotor_diameter_mm": 380,
        "compatible_platforms": ["BMW M3 E46/E90", "Porsche 911 996/997", "Nissan GT-R R35", "Ford Mustang S550"],
        "install_location": "front axle, replaces OEM caliper and rotor, requires specific wheel clearance (18in minimum)",
        "cost_usd": [2500, 4500],
        "supporting_mods": ["brake fluid upgrade (Motul RBF 660 or similar)", "stainless braided lines", "appropriate brake pads"],
        "known_issues": [
            "requires 18in wheels minimum for clearance",
            "dust shields may need modification",
            "brake bias may shift — rear upgrade recommended",
            "brake fluid must be changed to high temp spec"
        ],
        "tags": ["brake", "big_brake_kit", "track_capable", "premium"],
    },
    {
        "name": "StopTech Sport Drilled and Slotted Rotors",
        "manufacturer": "StopTech",
        "category": "brake",
        "type": "rotor upgrade",
        "compatible_platforms": ["universal — application specific"],
        "install_location": "direct OEM rotor replacement, all 4 corners",
        "cost_usd": [200, 400],
        "supporting_mods": ["performance brake pads", "brake fluid"],
        "known_issues": [
            "drilled rotors can crack under heavy track use — slotted only better for track",
            "excellent street upgrade",
            "upgrade pads when upgrading rotors"
        ],
        "tags": ["brake", "rotor", "street_track", "upgrade"],
    },
    {
        "name": "Hawk HPS Performance Brake Pads",
        "manufacturer": "Hawk",
        "category": "brake",
        "type": "brake pad",
        "compound": "HPS (High Performance Street)",
        "temp_range_c": [0, 480],
        "compatible_platforms": ["universal"],
        "install_location": "front and rear calipers, replace OEM pads",
        "cost_usd": [70, 130],
        "supporting_mods": ["none — direct replacement"],
        "known_issues": [
            "more dust than OEM but better performance",
            "good street and occasional track use",
            "DTC-60 or DTC-70 compound for serious track use"
        ],
        "tags": ["brake", "pad", "street", "performance", "universal"],
    },
    {
        "name": "Hawk DTC-60 Race Brake Pads",
        "manufacturer": "Hawk",
        "category": "brake",
        "type": "brake pad",
        "compound": "DTC-60 (race)",
        "temp_range_c": [120, 700],
        "compatible_platforms": ["universal"],
        "install_location": "front and rear calipers",
        "cost_usd": [120, 200],
        "supporting_mods": ["brake fluid upgrade mandatory (RBF 660+)", "warm up laps required"],
        "known_issues": [
            "cold braking performance poor — need heat in pads before full braking",
            "not suitable for street use — grabby when cold",
            "excellent sustained track performance"
        ],
        "tags": ["brake", "pad", "track", "race", "high_temp"],
    },
]

# ── Cooling ───────────────────────────────────────────────────────────────────

COOLING = [
    {
        "name": "Mishimoto Aluminum Performance Radiator",
        "manufacturer": "Mishimoto",
        "category": "cooling",
        "type": "radiator",
        "core_rows": 2,
        "compatible_platforms": ["Toyota Supra A80", "Nissan Skyline R32/R33/R34", "Subaru WRX/STI", "Honda Civic EG/EK"],
        "install_location": "OEM radiator location, direct replacement, uses OEM mounting points and hoses",
        "cost_usd": [250, 500],
        "supporting_mods": ["fresh coolant", "pressure test after install"],
        "known_issues": [
            "direct bolt-on on most applications",
            "significant improvement over aging OEM radiators",
            "lifetime warranty"
        ],
        "tags": ["cooling", "radiator", "bolt_on", "universal"],
    },
    {
        "name": "Setrab Oil Cooler Kit",
        "manufacturer": "Setrab",
        "category": "cooling",
        "type": "oil cooler",
        "rows": 13,
        "compatible_platforms": ["universal — requires fitting and line fabrication"],
        "install_location": "typically front of engine bay alongside radiator, or in front bumper opening, connected to engine oil circuit via sandwich plate adapter",
        "cost_usd": [300, 600],
        "supporting_mods": ["sandwich plate adapter", "AN fittings and lines", "thermostat recommended"],
        "known_issues": [
            "oil thermostat critical — without it oil temps drop too low in cold weather causing wear",
            "AN line routing must avoid heat sources",
            "significant help on sustained boost or track use"
        ],
        "tags": ["cooling", "oil_cooler", "universal", "track"],
    },
    {
        "name": "Greddy Turbo Oil Cooler Kit",
        "manufacturer": "Greddy",
        "category": "cooling",
        "type": "turbo oil cooler",
        "compatible_engines": ["2JZ-GTE", "RB26DETT", "SR20DET"],
        "install_location": "turbo oil feed/return circuit, mounts in front of engine bay",
        "cost_usd": [250, 450],
        "supporting_mods": ["AN fittings", "braided oil lines"],
        "known_issues": [
            "important on high power builds where turbo sees sustained heat",
            "reduces oil coking in turbo bearing housing"
        ],
        "tags": ["cooling", "oil_cooler", "turbo", "jdm"],
    },
]

# ── Aero ──────────────────────────────────────────────────────────────────────

AERO = [
    {
        "name": "Voltex Type 1S GT Wing",
        "manufacturer": "Voltex",
        "category": "aero",
        "type": "rear wing",
        "downforce_at_200kph_kg": 45,
        "drag_increase_pct": 8,
        "compatible_platforms": ["universal — custom mounting required"],
        "install_location": "rear trunk lid or dedicated wing mounts on chassis",
        "cost_usd": [1500, 2500],
        "supporting_mods": ["front splitter for aero balance", "trunk reinforcement may be required"],
        "known_issues": [
            "significant downforce at speed — improves high speed stability",
            "increases drag — top speed reduced",
            "front aero balance essential — rear wing without front splitter creates oversteer at speed"
        ],
        "tags": ["aero", "wing", "track", "downforce"],
    },
    {
        "name": "APR Performance GTC-200 Carbon Wing",
        "manufacturer": "APR Performance",
        "category": "aero",
        "type": "rear wing",
        "downforce_at_200kph_kg": 35,
        "drag_increase_pct": 6,
        "compatible_platforms": ["universal"],
        "install_location": "trunk or dedicated mounts",
        "cost_usd": [700, 1200],
        "supporting_mods": ["front lip or splitter recommended"],
        "known_issues": [
            "carbon fiber — lightweight",
            "adjustable angle of attack",
            "popular track day option"
        ],
        "tags": ["aero", "wing", "carbon", "track", "adjustable"],
    },
    {
        "name": "OEM Style Front Lip Splitter",
        "manufacturer": "Various",
        "category": "aero",
        "type": "front splitter",
        "downforce_at_200kph_kg": 15,
        "drag_increase_pct": 3,
        "compatible_platforms": ["application specific"],
        "install_location": "front bumper lower edge, clips or bolts to OEM bumper",
        "cost_usd": [150, 500],
        "supporting_mods": ["support rods to chassis"],
        "known_issues": [
            "ground clearance reduced — speed bumps become obstacles",
            "support rods mandatory — without them splitter flexes at speed"
        ],
        "tags": ["aero", "splitter", "front", "street_track"],
    },
]

# ── Lookup helpers ────────────────────────────────────────────────────────────

ALL_MODS = (
    TURBOS + SUPERCHARGERS + INTERCOOLERS +
    INJECTORS + FUEL_PUMPS +
    PISTONS + CONNECTING_RODS + HEAD_STUDS +
    COILOVERS + SWAY_BARS +
    WHEELS + TYRES +
    ECU_SYSTEMS + EXHAUSTS + BRAKES + COOLING + AERO
)

CATEGORY_MAP = {
    "turbo":            TURBOS,
    "supercharger":     SUPERCHARGERS,
    "intercooler":      INTERCOOLERS,
    "injector":         INJECTORS,
    "fuel_pump":        FUEL_PUMPS,
    "piston":           PISTONS,
    "connecting_rod":   CONNECTING_RODS,
    "head_stud":        HEAD_STUDS,
    "coilover":         COILOVERS,
    "sway_bar":         SWAY_BARS,
    "wheel":            WHEELS,
    "tyre":             TYRES,
    "ecu":              ECU_SYSTEMS,
    "exhaust":          EXHAUSTS,
    "brake":            BRAKES,
    "cooling":          COOLING,
    "aero":             AERO,
}


def find_mods_by_engine(engine_name, category=None):
    """Find mods compatible with a given engine name."""
    results = []
    search  = engine_name.upper()
    pool    = CATEGORY_MAP.get(category, ALL_MODS) if category else ALL_MODS
    for mod in pool:
        engines   = [e.upper() for e in mod.get("compatible_engines", [])]
        platforms = [p.upper() for p in mod.get("compatible_platforms", [])]
        if (any(search in e or e in search for e in engines) or
                any(search in p for p in platforms) or
                "UNIVERSAL" in engines or "UNIVERSAL" in platforms):
            results.append(mod)
    return results


def find_mods_by_hp_target(target_hp, category=None, engine_name=None):
    """Find mods that can support a given HP target."""
    results = []
    pool    = CATEGORY_MAP.get(category, ALL_MODS) if category else ALL_MODS
    for mod in pool:
        max_hp = mod.get("max_hp") or mod.get("max_hp_support")
        min_hp = mod.get("min_hp", 0)
        if max_hp and min_hp <= target_hp <= max_hp:
            if engine_name:
                engines = [e.upper() for e in mod.get("compatible_engines", [])]
                if (any(engine_name.upper() in e or e in engine_name.upper()
                        for e in engines) or not engines or "UNIVERSAL" in [e.upper() for e in mod.get("compatible_engines", [])]):
                    results.append(mod)
            else:
                results.append(mod)
    return results


def find_mods_by_tag(tag, engine_name=None):
    """Find mods by tag."""
    results = []
    for mod in ALL_MODS:
        if tag in mod.get("tags", []):
            if engine_name:
                engines = [e.upper() for e in mod.get("compatible_engines", [])]
                if (any(engine_name.upper() in e for e in engines) or
                        not engines):
                    results.append(mod)
            else:
                results.append(mod)
    return results


def get_supporting_mods(mod_name):
    """Get all supporting mods required for a given mod."""
    for mod in ALL_MODS:
        if mod["name"].lower() == mod_name.lower():
            return mod.get("supporting_mods", [])
    return []


def estimate_total_cost(mod_list, budget_tier="mid"):
    """
    Estimate total cost for a list of mods.
    budget_tier: 'low', 'mid', 'high'
    """
    total = 0
    breakdown = []
    idx = {"low": 0, "mid": 0, "high": 1}[budget_tier]
    for mod in mod_list:
        cost_range = (mod.get("cost_usd") or
                      [mod.get("cost_usd_per_tyre", [0, 0])[0] * 4,
                       mod.get("cost_usd_per_tyre", [0, 0])[1] * 4])
        if cost_range and len(cost_range) >= 2:
            cost = cost_range[idx]
            total += cost
            breakdown.append({"mod": mod["name"], "cost": cost})
    return total, breakdown


if __name__ == "__main__":
    print(f"Total mods in knowledge base: {len(ALL_MODS)}")
    print(f"\nBy category:")
    for cat, mods in CATEGORY_MAP.items():
        print(f"  {cat:20} {len(mods)} mods")

    print(f"\n2JZ compatible mods:")
    for m in find_mods_by_engine("2JZ"):
        print(f"  {m['name']} — ${m.get('cost_usd', ['?','?'])[0]}-{m.get('cost_usd', ['?','?'])[-1]}")

    print(f"\nMods supporting 500hp target:")
    for m in find_mods_by_hp_target(500):
        print(f"  {m['name']} ({m['category']})")
