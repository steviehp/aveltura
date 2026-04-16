"""
physics_query.py — Natural Language Physics Query Parser

Converts natural language queries into physics engine calls.
Routes to the correct module and formats output for chat.

Query types detected:
  aero       — "what is the drag on a Supra at 200kph"
  wind tunnel — "run a wind tunnel test on my Supra"
  tyre       — "analyse my tyre setup" / "what compound should I use"
  thermal    — "will my brakes overheat" / "is my cooling enough"
  structural — "will my roll cage hold" / "what material for a wing"
  dynamics   — "what is the understeer gradient" / "lap time at Suzuka"
  optimize   — "optimize my setup for lap time at Tsukuba"
  material   — "what is the best material for a splitter"
"""

import re
import os
import sys
import logging

BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "physics_engine"))

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "physics.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ── Query type detection ──────────────────────────────────────────────────────

QUERY_PATTERNS = {
    "optimize": [
        r"optimis[ez]", r"optimize", r"best setup", r"fastest setup",
        r"optimal", r"tune for", r"set up for",
    ],
    "wind_tunnel": [
        r"wind tunnel", r"aero sweep", r"yaw sweep", r"tunnel test",
    ],
    "aero": [
        r"drag", r"downforce", r"aerodynam", r"cd\b", r"lift",
        r"wing force", r"aero force", r"terminal velocity", r"top speed",
    ],
    "tyre": [
        r"tyre", r"tire", r"grip", r"compound", r"slip angle",
        r"contact patch", r"warmup", r"traction",
    ],
    "thermal": [
        r"overheat", r"cooling", r"temperature", r"brake fade",
        r"fluid boil", r"thermal", r"intercooler", r"turbo temp",
        r"tit\b", r"egt\b",
    ],
    "structural": [
        r"stress", r"fatigue", r"buckling", r"safety factor",
        r"roll cage", r"material strength", r"yield", r"deflect",
    ],
    "material": [
        r"material", r"what.*made of", r"carbon fibre", r"aluminium",
        r"steel", r"composite", r"lightest", r"strongest",
    ],
    "dynamics": [
        r"lap time", r"understeer", r"oversteer", r"handling",
        r"weight transfer", r"roll angle", r"cornering", r"balance",
        r"circuit", r"suzuka", r"tsukuba", r"spa\b", r"nurburgring",
    ],
}


def detect_query_type(query: str) -> str:
    q = query.lower()
    for qtype in ["optimize", "wind_tunnel", "dynamics", "thermal",
                  "structural", "material", "tyre", "aero"]:
        patterns = QUERY_PATTERNS[qtype]
        if any(re.search(p, q) for p in patterns):
            return qtype
    return "aero"


def extract_velocity(query: str, default: float = 200.0) -> float:
    q = query.lower()
    m = re.search(r'(\d+)\s*(?:kph|km/h|kmh)', q)
    if m:
        return float(m.group(1))
    m = re.search(r'(\d+)\s*(?:mph)', q)
    if m:
        return float(m.group(1)) * 1.609
    m = re.search(r'(\d+)\s*(?:m/s|ms)', q)
    if m:
        return float(m.group(1)) * 3.6
    return default


def extract_circuit(query: str) -> str:
    q = query.lower()
    circuit_map = {
        "suzuka":        "suzuka",
        "tsukuba":       "tsukuba",
        "nurburgring":   "nurburgring_gp",
        "nurburg":       "nurburgring_gp",
        "brands hatch":  "brands_hatch",
        "brands":        "brands_hatch",
        "laguna seca":   "laguna_seca",
        "laguna":        "laguna_seca",
        "willow springs":"willow_springs",
        "willow":        "willow_springs",
        "spa":           "spa",
        "bathurst":      "bathurst",
    }
    for keyword, key in circuit_map.items():
        if keyword in q:
            return key
    return "tsukuba"


def extract_goal(query: str) -> str:
    q = query.lower()
    if any(x in q for x in ["lap time", "fastest lap", "circuit", "track"]):
        return "lap_time"
    if any(x in q for x in ["top speed", "terminal velocity", "straight line"]):
        return "top_speed"
    if any(x in q for x in ["downforce", "grip", "cornering"]):
        return "downforce"
    if any(x in q for x in ["balance", "neutral", "handling", "understeer", "oversteer"]):
        return "balance"
    if any(x in q for x in ["efficiency", "fuel", "economy"]):
        return "efficiency"
    return "lap_time"


def extract_compound(query: str) -> str:
    """Extract tyre compound — semi-slick checked before generic slick."""
    q = query.lower()
    if any(x in q for x in ["slick soft", "qualifying"]):
        return "slick_soft"
    # Semi-slick BEFORE generic slick to avoid false match
    if any(x in q for x in ["semi slick", "semi-slick", "200tw", "cup 2", "a052"]):
        return "semi_slick"
    if any(x in q for x in ["slick medium", "slick"]):
        return "slick_medium"
    if any(x in q for x in ["performance", "ps4s", "sport plus", "300tw"]):
        return "performance_street"
    return "performance_street"


def extract_material_application(query: str) -> str:
    q = query.lower()
    for app in ["wing", "splitter", "chassis", "roll cage", "wheel",
                "brake disc", "suspension arm", "exhaust", "connecting rod",
                "body panel"]:
        if app in q:
            return app
    return "body panel"


# ── Default vehicle spec ──────────────────────────────────────────────────────

def build_default_supra():
    from aerodynamics import VehicleGeometry
    from vehicle_dynamics import VehicleSpec

    geom = VehicleGeometry(
        length_m=4.515, width_m=1.810, height_m=1.275,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        ride_height_m=0.110, windscreen_rake_deg=28, body_style="fastback",
        baseline_cd=0.31, baseline_cl=0.18,
        has_rear_wing=True, wing_span_m=1.300, wing_chord_m=0.250,
        wing_aoa_deg=10.0, wing_profile="NACA2412",
        has_front_splitter=True, splitter_length_m=0.070, splitter_width_m=1.500,
        has_underbody_diffuser=True, diffuser_angle_deg=7.0,
    )
    spec = VehicleSpec(
        name="Toyota Supra MK4",
        drivetrain="rwd",
        mass_kg=1520, fuel_mass_kg=40, driver_mass_kg=75,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        cog_height_m=0.45, weight_dist_front=0.52,
        roll_stiffness_front_nm_deg=1400, roll_stiffness_rear_nm_deg=900,
        camber_front_deg=-2.0, camber_rear_deg=-1.5,
        engine_power_hp=588,
        tyre_compound="semi_slick",
        brake_bias_front=0.65,
        aero_geometry=geom,
    )
    return spec, geom


# ── Query handlers ────────────────────────────────────────────────────────────

def handle_aero(query: str) -> str:
    from aerodynamics import aerodynamic_forces, solve_terminal_velocity
    spec, geom = build_default_supra()
    v_kph = extract_velocity(query)
    v_ms  = v_kph / 3.6

    r = aerodynamic_forces(geom, v_ms)
    lines = [
        f"**Aerodynamic Analysis — Toyota Supra MK4 at {v_kph:.0f}kph**\n",
        f"Drag coefficient (Cd): {r['cd']}",
        f"Lift coefficient (Cl): {r['cl']} ({'downforce' if r['cl'] < 0 else 'lift'})",
        f"",
        f"**Forces:**",
        f"  Drag:       {r['drag_kg']}kg ({r['drag_n']}N)",
        f"  Downforce:  {r['downforce_kg']}kg ({r['downforce_n']}N)",
        f"  Front DF:   {r['front_downforce_kg']}kg",
        f"  Rear DF:    {r['rear_downforce_kg']}kg",
        f"",
        f"**Power consumption:**",
        f"  Drag power: {r['drag_power_hp']}hp ({r['drag_power_kw']}kW) just to push air",
        f"",
        f"**Flow conditions:**",
        f"  Reynolds number: {r['reynolds_number']:,.0f}",
        f"  Flow regime:     {r['flow_regime']}",
        f"  Dynamic pressure:{r['dynamic_pressure_pa']}Pa",
    ]

    if r['wing_forces']:
        wf = r['wing_forces']
        lines += [
            f"",
            f"**Rear Wing ({geom.wing_aoa_deg}° AoA):**",
            f"  Downforce: {wf['downforce_kg']}kg",
            f"  Drag:      {wf['drag_kg']}kg",
            f"  L/D ratio: {wf['l_d_ratio']}",
            f"  {'⚠ STALL WARNING' if wf['stall_warning'] else 'No stall risk'}",
        ]

    vmax = solve_terminal_velocity(
        spec.engine_power_hp * 745.7 / 1000, geom,
        vehicle_mass_kg=spec.total_mass_kg, drivetrain_efficiency=0.82,
    )
    lines.append(f"\n**Terminal velocity:** {round(vmax*3.6,1)}kph")
    return "\n".join(lines)


def handle_wind_tunnel(query: str) -> str:
    from aerodynamics import virtual_wind_tunnel
    _, geom = build_default_supra()
    v_kph   = extract_velocity(query, 200.0)

    result = virtual_wind_tunnel(
        geom,
        velocities_kph=[80, 120, 160, 200, 240] if v_kph >= 200 else [60, 80, 120, 160, v_kph],
        yaw_angles_deg=[0, 5, 10],
    )

    tc = result["tunnel_conditions"]
    lines = [
        f"**Virtual Wind Tunnel — Toyota Supra MK4**\n",
        f"Tunnel cross-section: 5×5m (25m²)",
        f"Blockage ratio: {tc['blockage_ratio_pct']}% "
        f"({'OK — results accurate' if tc['blockage_ok'] else 'HIGH — blockage correction applied'})",
        f"Air density: {tc['air_density_kg_m3']} kg/m³",
        f"",
        f"**Test Matrix (0° yaw):**",
        f"{'kph':>8} {'Cd':>8} {'Drag kg':>10} {'Downforce kg':>14} {'Drag power hp':>14}",
        "-" * 60,
    ]

    for row in result["test_matrix"]:
        if row["yaw_deg"] == 0:
            lines.append(
                f"{row['velocity_kph']:>8.0f} {row['cd']:>8.4f} "
                f"{row['drag_kg']:>10.1f} {row['downforce_kg']:>14.1f} "
                f"{row['drag_power_hp']:>14.1f}"
            )

    lines += [
        f"",
        f"**Crosswind sensitivity (at 200kph):**",
        f"{'Yaw deg':>10} {'Cd':>8} {'Side force N':>14}",
        "-" * 40,
    ]
    for row in result["test_matrix"]:
        if row["velocity_kph"] == 200:
            lines.append(
                f"{row['yaw_deg']:>10.0f} {row['cd']:>8.4f} {row['side_n']:>14.1f}"
            )

    lines += [
        f"",
        f"**Summary:**",
        f"  Cd range:       {result['summary']['cd_min']} – {result['summary']['cd_max']}",
        f"  Peak downforce: {result['summary']['max_downforce_kg']}kg",
        f"  Peak drag:      {result['summary']['max_drag_kg']}kg",
    ]
    return "\n".join(lines)


def handle_tyre(query: str) -> str:
    from tyre_model import analyse_tyre
    compound = extract_compound(query)
    result   = analyse_tyre(
        compound, "265/35R19",
        vehicle_mass_kg=1635, cog_height_m=0.45,
        track_width_m=1.52, wheelbase_m=2.55,
        aero_downforce_n=400.0,
    )
    cp  = result["contact_patch"]
    gr  = result["grip"]
    vl  = result["vehicle_limits"]
    wu  = result["warmup"]
    sa  = result["slip_angle_analysis"]

    lines = [
        f"**Tyre Analysis — {compound.replace('_',' ').title()} — {result['tyre_size']['size']}**\n",
        f"**Contact Patch:**",
        f"  Area:     {cp['area_cm2']}cm² ({cp['length_mm']}mm × {cp['width_mm']}mm)",
        f"",
        f"**Temperature:**",
        f"  Peak grip temp:  {result['peak_grip_temp_c']}°C",
        f"  Operating temp:  {result['operating_temp_c']}°C",
        f"  Temp factor:     {result['temp_factor']} ({round(result['temp_factor']*100)}% of peak grip)",
        f"",
        f"**Grip:**",
        f"  Peak lateral μ:       {gr['peak_lateral_mu']}",
        f"  Peak longitudinal μ:  {gr['peak_longitudinal_mu']}",
        f"  Peak combined μ:      {gr['peak_combined_mu']}",
        f"",
        f"**Vehicle Performance Limits:**",
        f"  Max lateral accel:   {vl['max_lateral_accel_g']}g",
        f"  Max braking:         {vl['max_braking_g']}g",
        f"  Lateral force:       {vl['lateral_force_n']:,.0f}N",
        f"",
        f"**Slip Angle:**",
        f"  Peak slip angle:     {sa['peak_slip_angle_deg']}°",
        f"  Cornering stiffness: {sa['cornering_stiffness']:.3f} μ/deg",
        f"",
        f"**Warmup:**",
        f"  Time to optimal temp: {wu['time_to_optimal_s']}",
        f"  Cold grip fraction:   {round(wu['cold_grip_fraction']*100)}% of peak",
        f"",
        f"**Compound comparison at this setup:**",
    ]

    from tyre_model import TYRE_COMPOUNDS
    for comp_name in ["slick_soft", "slick_medium", "semi_slick", "performance_street", "standard_street"]:
        try:
            r2 = analyse_tyre(comp_name, "265/35R19", 1635, 0.45, 1.52, 2.55, 400.0)
            wu2 = r2["warmup"]
            marker = " <-- selected" if comp_name == compound else ""
            lines.append(
                f"  {comp_name:20} max_lat={r2['vehicle_limits']['max_lateral_accel_g']}g  "
                f"warmup={wu2['time_to_optimal_s']}{marker}"
            )
        except Exception:
            pass

    return "\n".join(lines)


def handle_thermal(query: str) -> str:
    from thermodynamics import full_thermal_analysis, BrakeDisc, CoolingSystem
    front_disc = BrakeDisc(0.155, 0.070, 0.028, 36)
    rear_disc  = BrakeDisc(0.140, 0.065, 0.022, 24)
    cooling    = CoolingSystem(
        radiator_area_m2=0.42, n_rows=2,
        has_oil_cooler=True, oil_cooler_area_m2=0.06,
        has_intercooler=True, intercooler_efficiency=0.88,
        coolant_flow_lpm=90,
    )
    result = full_thermal_analysis(
        engine_power_hp=588, boost_psi=22,
        displacement_cc=2998, compression_ratio=8.5,
        vehicle_mass_kg=1520, cooling=cooling,
        front_disc=front_disc, rear_disc=rear_disc,
        v_max_kph=270, ambient_temp_c=25.0,
        brake_fluid="Motul RBF660",
    )

    eng = result["engine_heat"]
    cr  = result["cooling_highway"]
    cl  = result["cooling_low_speed"]
    tit = result["turbo_temperatures"]
    ic  = result["intercooler"]
    br  = result["braking"]

    lines = [
        f"**Full Thermal Analysis — Toyota Supra MK4 500whp**\n",
        f"**Engine Heat Rejection ({result['engine_power_hp']}hp):**",
        f"  Total heat:      {round(eng['heat_rejected_w']/1000,1)}kW",
        f"  To coolant:      {round(eng['heat_to_coolant_w']/1000,1)}kW",
        f"  To exhaust:      {round(eng['heat_to_exhaust_w']/1000,1)}kW",
        f"",
        f"**Cooling System:**",
        f"  Highway SS temp: {cr['coolant_steady_state_c']}°C {'✓' if not cr['overheat_risk'] else '⚠ OVERHEAT'}",
        f"  Traffic SS temp: {cl['coolant_steady_state_c']}°C {'✓' if not cl['overheat_risk'] else '⚠ OVERHEAT — add oil cooler'}",
        f"  Airflow:         {cr['airflow_velocity_ms']}m/s at radiator face",
        f"  Margin:          {cr['margin_w']/1000:.1f}kW at highway",
        f"",
        f"**Turbocharger:**",
        f"  Turbine inlet:   {tit['turbine_inlet_temp_c']}°C",
        f"  Lambda:          {tit['lambda']}",
        f"  Oil coking risk: {'⚠ YES — use turbo timer' if tit['oil_coking_risk'] else 'No'}",
        f"",
        f"**Intercooler ({ic['boost_psi']}psi boost):**",
        f"  Compressor out:  {ic['compressor_outlet_temp_c']}°C",
        f"  IC outlet:       {ic['intercooler_outlet_temp_c']}°C  (drop: {ic['temperature_drop_c']}°C)",
        f"  Power gain:      {ic['estimated_power_gain_pct']}% vs no intercooler",
        f"  Knock risk:      {'⚠ YES' if ic['knock_risk'] else 'No'}",
        f"",
        f"**Braking (270kph → 60kph):**",
        f"  Heat generated:  {br['braking_event']['total_heat_kj']}kJ",
        f"  Front disc:      {br['temperatures']['front_disc_c']}°C",
        f"  Rear disc:       {br['temperatures']['rear_disc_c']}°C",
        f"  Fluid est:       {br['temperatures']['fluid_est_c']}°C",
        f"  Boiling risk:    {'⚠ YES — upgrade fluid' if br['risk_assessment']['boiling_risk'] else 'No'}",
        f"  → {br['risk_assessment']['recommendation']}",
        f"",
        f"**Critical Issues:**",
    ]
    for issue in result["critical_issues"]:
        sym = "⚠" if any(x in issue for x in ["OVERHEAT","TURBO","BRAKES","CRITICAL"]) else "✓"
        lines.append(f"  {sym} {issue}")

    return "\n".join(lines)


def handle_structural(query: str) -> str:
    from structural import (analyse_roll_cage_tube, aero_panel_stress,
                             optimize_material)
    lines = [f"**Structural Analysis — Roll Cage and Aero Surfaces**\n"]

    lines.append("**Roll Cage Tube Analysis (5000N side load, 1.2m span):**")
    lines.append(f"  {'Tube':15} {'Material':35} {'SF bend':>8} {'SF buckle':>10} {'FIA':>5} {'kg/m':>6}")
    lines.append("  " + "-" * 83)
    for od, wall, mat in [
        (38, 2.5, "Chromoly Steel (4130)"),
        (40, 2.0, "Chromoly Steel (4130)"),
        (45, 3.0, "High Strength Steel (AISI 4340)"),
    ]:
        r = analyse_roll_cage_tube(od, wall, 1.2, mat, load_n=5000)
        lines.append(
            f"  {r['tube_size']:15} {mat[:33]:35} "
            f"{r['bending']['safety_factor']:>8.2f} "
            f"{r['buckling']['safety_factor']:>10.2f} "
            f"{'✓' if r['fia_compliance'] else '✗':>5} "
            f"{r['mass_per_metre_kg']:>6.3f}"
        )

    lines.append(f"\n**Rear Wing Panel (45kg downforce, NACA2412, 1400×250×3mm):**")
    force    = 45 * 9.81
    pressure = force / (1.4 * 0.25)
    for mat in ["Carbon Fibre UD Prepreg (T700/Epoxy)",
                "Aluminium 6061-T6",
                "Fibreglass (E-Glass/Epoxy)"]:
        r = aero_panel_stress(pressure, 0.25, 1.4, 0.003, mat)
        if "error" not in r:
            lines.append(
                f"  {mat[:45]:45} σ={r['max_stress_mpa']:6.1f}MPa  "
                f"SF={r['safety_factor']:6.2f}  "
                f"δ={r['max_deflection_mm']:.2f}mm  "
                f"{'PASS' if not r['will_yield'] else 'FAIL'}"
            )

    lines.append(f"\n**Lightest tube for 800N bending, 600mm span, SF≥2:**")
    results = optimize_material(150, 800, 0.6, "bending", optimize_for="weight")
    for r in results[:4]:
        lines.append(
            f"  {r['material'][:45]:45} {r['tube_size']:20} "
            f"{r['mass_kg_per_m']:.4f}kg/m  ${r['cost_usd_per_m']:.2f}/m"
        )

    return "\n".join(lines)


def handle_material(query: str) -> str:
    from materials_db import best_material_for, MATERIALS
    application = extract_material_application(query)
    mats        = best_material_for(application)

    lines = [f"**Material Selection — {application.title()}**\n"]
    lines.append(
        f"  {'Material':45} {'Yield MPa':>10} {'Density':>9} "
        f"{'E GPa':>7} {'$/kg':>7} {'Spec σ kN/kg':>13}"
    )
    lines.append("  " + "-" * 96)

    for m in mats:
        lines.append(
            f"  {m.name[:43]:45} "
            f"{round(m.yield_strength_pa/1e6):>10.0f} "
            f"{m.density_kg_m3:>9.0f} "
            f"{round(m.elastic_modulus_pa/1e9,1):>7.1f} "
            f"{m.cost_usd_per_kg:>7.1f} "
            f"{round(m.specific_strength/1e3,0):>13.0f}"
        )

    if mats:
        best = mats[0]
        lines += [
            f"",
            f"**Recommendation:** {best.name}",
            f"  {best.notes}",
            f"  Common uses:          {', '.join(best.common_uses[:4])}",
            f"  Weldability:          {best.weldability}",
            f"  Machinability:        {best.machinability}",
            f"  Corrosion resistance: {best.corrosion_resistance}",
            f"  Max service temp:     {round(best.max_service_temp_k - 273.15)}°C",
        ]

    return "\n".join(lines)


def handle_dynamics(query: str) -> str:
    from vehicle_dynamics import full_vehicle_analysis, simulate_lap, CIRCUITS
    circuit_key = extract_circuit(query)
    circuit     = CIRCUITS.get(circuit_key, CIRCUITS["tsukuba"])
    # Default to semi_slick for dynamics — more realistic for track analysis
    compound    = extract_compound(query) if any(x in query.lower() for x in ["slick","street","compound","tyre","tire"]) else "semi_slick"
    spec, _     = build_default_supra()

    result = full_vehicle_analysis(spec, compound, velocity_kph=150.0,
                                   lateral_accel_g=1.5, braking_g=1.2)
    lap    = simulate_lap(spec, compound, circuit["corners"],
                          circuit["straight_m"], circuit["name"])

    bal = result["balance"]
    pl  = result["performance_limits"]
    wt  = result["weight_transfer"]["cornering"]
    sus = result["suspension"]

    lines = [
        f"**Vehicle Dynamics — Toyota Supra MK4 500whp**\n",
        f"**Handling Balance ({compound.replace('_',' ').title()}):**",
        f"  Understeer gradient: {bal['understeer_gradient_deg_g']} deg/g",
        f"  Balance:             {bal['balance']}",
        f"  → {bal['recommendation']}",
        f"",
        f"**Performance Limits:**",
        f"  Max lateral accel:   {pl['max_lateral_g']}g",
        f"  Max braking:         {pl['max_braking_g']}g",
        f"  Max acceleration:    {pl['max_accel_g']}g",
        f"",
        f"**Weight Transfer (1.5g cornering):**",
        f"  Total lateral transfer: {wt['total_transfer_n']}N",
        f"  Outer front load:       {wt['outer_front_n']}N",
        f"  Outer rear load:        {wt['outer_rear_n']}N",
        f"  Inner front load:       {wt['inner_front_n']}N (unloaded)",
        f"",
        f"**Suspension:**",
        f"  Roll angle:      {sus['roll_angle_deg']}°",
        f"  Outer front cam: {sus['front_camber']['outer_tyre_deg']}°",
        f"  Outer rear cam:  {sus['rear_camber']['outer_tyre_deg']}°",
        f"",
        f"**Lap Time — {circuit['name']} ({circuit['country']}, {circuit['length_m']}m):**",
        f"  Estimated lap: {lap['lap_time_str']}",
        f"  Avg speed:     {lap['avg_speed_kph']}kph",
        f"",
        f"  Corner breakdown:",
    ]
    for s in lap["sectors"]:
        lines.append(
            f"    {s['corner']:22} v={s['v_corner_kph']:5.1f}kph  "
            f"lat={s['lateral_accel_g']:.2f}g  t={s['sector_time_s']:.2f}s"
        )

    return "\n".join(lines)


def handle_optimize(query: str) -> str:
    from optimizer import optimize, format_result
    goal        = extract_goal(query)
    circuit_key = extract_circuit(query)
    compound    = extract_compound(query)
    v_kph       = extract_velocity(query, 200.0)
    spec, _     = build_default_supra()

    result = optimize(
        spec, goal,
        compound_name=compound,
        circuit_key=circuit_key,
        velocity_kph=v_kph,
        max_iterations=300,
    )
    return format_result(result)


# ── Main entry point ──────────────────────────────────────────────────────────

def physics_query(query: str) -> str:
    """Route natural language query to correct physics handler."""
    logging.info(f"Physics query: {query[:100]}")
    qtype = detect_query_type(query)
    logging.info(f"Detected query type: {qtype}")

    try:
        handlers = {
            "optimize":    handle_optimize,
            "wind_tunnel": handle_wind_tunnel,
            "aero":        handle_aero,
            "tyre":        handle_tyre,
            "thermal":     handle_thermal,
            "structural":  handle_structural,
            "material":    handle_material,
            "dynamics":    handle_dynamics,
        }
        return handlers.get(qtype, handle_aero)(query)
    except Exception as e:
        logging.error(f"Physics query error: {e}", exc_info=True)
        return (
            f"Physics engine error: {e}\n\n"
            f"Try:\n"
            f"  'What is the drag on a Supra at 200kph'\n"
            f"  'Run a wind tunnel test'\n"
            f"  'Analyse the semi-slick tyre setup'\n"
            f"  'Will the brakes and cooling hold up on track?'\n"
            f"  'What is the best material for a rear wing?'\n"
            f"  'What is the lap time at Tsukuba?'\n"
            f"  'Optimize the setup for lap time at Tsukuba'"
        )


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_queries = [
        "What is the drag and downforce on a Supra at 200kph?",
        "Run a wind tunnel test on the Supra",
        "Analyse the semi-slick tyre setup",
        "Will the brakes and cooling hold up on track?",
        "What is the best material for a carbon fibre rear wing?",
        "What is the understeer gradient and lap time at Tsukuba?",
        "Optimize the setup for lap time at Tsukuba",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        print(physics_query(query))
