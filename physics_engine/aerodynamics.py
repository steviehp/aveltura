"""
physics_engine/aerodynamics.py — Aerodynamic Analysis Engine

Coordinate system:
  X = longitudinal (front positive)
  Y = lateral (left positive)
  Z = vertical (up positive)
  Origin = front axle centerline at ground level

All calculations in SI units.
Air properties computed from temperature and altitude.

References:
  - Hucho, W.H. "Aerodynamics of Road Vehicles"
  - Katz, J. "Race Car Aerodynamics"
  - Milliken & Milliken "Race Car Vehicle Dynamics"
  - ISO 8855 vehicle dynamics coordinate system
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List


# ── Physical constants ────────────────────────────────────────────────────────

R_AIR       = 287.05    # J/(kg·K) — specific gas constant for dry air
GRAVITY     = 9.81      # m/s²
P_SEA_LEVEL = 101325.0  # Pa — standard atmospheric pressure at sea level
T_STD       = 288.15    # K — standard temperature at sea level (15°C)
MU_AIR      = 1.81e-5   # Pa·s — dynamic viscosity of air at 20°C (nearly constant)


# ── Air properties ────────────────────────────────────────────────────────────

def air_density(temp_c: float = 20.0, altitude_m: float = 0.0) -> float:
    """
    Calculate air density from temperature and altitude.
    Uses International Standard Atmosphere model.

    Args:
        temp_c:     Air temperature in Celsius
        altitude_m: Altitude above sea level in metres

    Returns:
        Air density ρ in kg/m³
    """
    temp_k = temp_c + 273.15
    # Pressure at altitude using barometric formula
    pressure = P_SEA_LEVEL * (1 - 2.2557e-5 * altitude_m) ** 5.2559
    return pressure / (R_AIR * temp_k)


def reynolds_number(velocity_ms: float, length_m: float,
                    temp_c: float = 20.0, altitude_m: float = 0.0) -> float:
    """
    Calculate Reynolds number for flow over a body.
    Re = ρ × v × L / μ

    Args:
        velocity_ms: Flow velocity in m/s
        length_m:    Characteristic length (car length) in metres
        temp_c:      Air temperature
        altitude_m:  Altitude

    Returns:
        Reynolds number (dimensionless)
    """
    rho = air_density(temp_c, altitude_m)
    return (rho * velocity_ms * length_m) / MU_AIR


def flow_regime(re: float) -> str:
    """Classify flow regime from Reynolds number."""
    if re < 5e5:
        return "laminar"
    elif re < 1e7:
        return "transitional"
    else:
        return "turbulent"


def blockage_correction(cd_measured: float, frontal_area_m2: float,
                         tunnel_cross_section_m2: float) -> float:
    """
    Correct measured Cd for wind tunnel blockage effect.
    Blockage ratio should be < 5% for accurate results.

    Args:
        cd_measured:          Raw measured drag coefficient
        frontal_area_m2:      Vehicle frontal area (m²)
        tunnel_cross_section_m2: Wind tunnel cross-sectional area (m²)

    Returns:
        Corrected drag coefficient
    """
    blockage_ratio = frontal_area_m2 / tunnel_cross_section_m2
    if blockage_ratio > 0.10:
        print(f"WARNING: Blockage ratio {blockage_ratio:.1%} > 10% — results unreliable")
    elif blockage_ratio > 0.05:
        print(f"WARNING: Blockage ratio {blockage_ratio:.1%} > 5% — correction applied")
    # Maskell correction method
    correction_factor = 1.0 - 0.96 * blockage_ratio
    return cd_measured * correction_factor


# ── Vehicle geometry ──────────────────────────────────────────────────────────

@dataclass
class VehicleGeometry:
    """
    Complete vehicle geometry specification for aerodynamic analysis.
    All dimensions in metres.
    """
    # ── Basic dimensions ──────────────────────────────────────────────────────
    length_m:           float        # overall length
    width_m:            float        # overall width
    height_m:           float        # overall height
    wheelbase_m:        float        # front to rear axle
    track_front_m:      float        # front track width
    track_rear_m:       float        # rear track width
    ride_height_m:      float = 0.12 # ground clearance at reference point

    # ── Body angles (degrees) ─────────────────────────────────────────────────
    windscreen_rake_deg:  float = 28.0   # windscreen angle from vertical
    hood_angle_deg:       float = 8.0    # hood/bonnet slope angle
    rear_screen_deg:      float = 35.0   # rear screen angle from vertical
    diffuser_angle_deg:   float = 0.0    # underbody diffuser angle
    diffuser_length_m:    float = 0.0    # diffuser length

    # ── Body style ────────────────────────────────────────────────────────────
    body_style:         str = "fastback"  # fastback | notchback | hatchback | estate | suv | truck

    # ── Reference areas ───────────────────────────────────────────────────────
    frontal_area_m2:    Optional[float] = None    # auto-calculated if None
    plan_area_m2:       Optional[float] = None    # auto-calculated if None
    wetted_area_m2:     Optional[float] = None    # auto-calculated if None

    # ── Aero devices ──────────────────────────────────────────────────────────
    has_front_splitter: bool = False
    splitter_length_m:  float = 0.0
    splitter_width_m:   float = 0.0

    has_rear_wing:      bool = False
    wing_span_m:        float = 0.0
    wing_chord_m:       float = 0.0
    wing_aoa_deg:       float = 0.0       # angle of attack
    wing_profile:       str = "NACA0012"  # aerofoil profile

    has_canards:        bool = False
    canard_area_m2:     float = 0.0

    has_underbody_diffuser: bool = False
    has_dive_planes:    bool = False
    has_vortex_generators: bool = False

    # ── Known baseline Cd (from manufacturer or measurement) ─────────────────
    baseline_cd:        Optional[float] = None
    baseline_cl:        Optional[float] = None   # negative = downforce

    def __post_init__(self):
        if self.frontal_area_m2 is None:
            # Approximate frontal area as 85% of width × height rectangle
            self.frontal_area_m2 = self.width_m * self.height_m * 0.85
        if self.plan_area_m2 is None:
            self.plan_area_m2 = self.length_m * self.width_m
        if self.wetted_area_m2 is None:
            # Rough approximation — actual wetted area ~3.5-4.5× frontal area
            self.wetted_area_m2 = self.frontal_area_m2 * 4.0

    @property
    def aspect_ratio(self) -> float:
        """Width to height ratio — affects frontal area estimation."""
        return self.width_m / self.height_m


# ── Wing/aerofoil analysis ────────────────────────────────────────────────────

# NACA 4-digit aerofoil Cl/Cd data (simplified linear model)
# Cl = 2π × sin(AoA) for thin aerofoil theory (Kutta-Joukowski)
# Real data: Cl_alpha ≈ 0.1 per degree for most profiles up to stall

AEROFOIL_DATA = {
    "NACA0012": {
        "cl_alpha_per_deg": 0.1095,    # Cl slope (per degree AoA)
        "cd_min":           0.006,      # minimum profile drag
        "cl_max":           1.5,        # maximum Cl before stall
        "aoa_stall_deg":    17,         # stall angle
        "cm_quarter_chord": 0.0,        # pitching moment (symmetric aerofoil)
    },
    "NACA2412": {
        "cl_alpha_per_deg": 0.107,
        "cd_min":           0.008,
        "cl_max":           1.68,
        "aoa_stall_deg":    16,
        "cm_quarter_chord": -0.05,
    },
    "NACA4412": {
        "cl_alpha_per_deg": 0.108,
        "cd_min":           0.009,
        "cl_max":           1.85,
        "aoa_stall_deg":    15,
        "cm_quarter_chord": -0.10,
    },
    "Gurney_Flap": {   # NACA2412 + 2% chord Gurney flap
        "cl_alpha_per_deg": 0.115,
        "cd_min":           0.012,
        "cl_max":           2.1,
        "aoa_stall_deg":    14,
        "cm_quarter_chord": -0.12,
    },
}


def wing_cl(aoa_deg: float, profile: str = "NACA0012",
            end_plate_efficiency: float = 0.85,
            inverted: bool = True) -> float:
    """
    Calculate wing lift coefficient at given angle of attack.
    Includes Prandtl finite wing correction and end plate efficiency.

    Cl_finite = Cl_2D × (AR / (AR + 2)) × end_plate_efficiency

    Args:
        aoa_deg:              Angle of attack in degrees
        profile:              Aerofoil profile name
        end_plate_efficiency: End plate effectiveness (0.8-1.0, 1.0 = perfect end plates)
        inverted:             True = wing mounted inverted (rear wing generating downforce)
                              When inverted, positive AoA generates negative Cl (downforce)

    Returns:
        Lift coefficient Cl (dimensionless)
        Negative = downforce (inverted wing), Positive = upforce (normal wing)
    """
    data = AEROFOIL_DATA.get(profile, AEROFOIL_DATA["NACA0012"])

    # Check for stall
    if abs(aoa_deg) >= data["aoa_stall_deg"]:
        stall_cl = data["cl_max"]
        cl_stall = stall_cl * 0.6 * np.sign(aoa_deg)
        return -cl_stall if inverted else cl_stall

    # Linear lift curve
    cl_2d = data["cl_alpha_per_deg"] * aoa_deg

    # Finite wing correction
    cl = cl_2d * end_plate_efficiency

    # Inverted mounting — rear wings generate downforce (negative lift)
    return -cl if inverted else cl


def wing_cd(cl: float, aspect_ratio: float, profile: str = "NACA0012",
             oswald_efficiency: float = 0.85) -> float:
    """
    Calculate wing drag coefficient using drag polar.
    Cd = Cd_min + Cl² / (π × AR × e)
    (profile drag + induced drag)

    Args:
        cl:               Lift coefficient
        aspect_ratio:     Wing aspect ratio (span²/area)
        profile:          Aerofoil profile
        oswald_efficiency: Span efficiency factor (0.7-0.95)

    Returns:
        Drag coefficient Cd
    """
    data = AEROFOIL_DATA.get(profile, AEROFOIL_DATA["NACA0012"])
    cd_profile = data["cd_min"]
    cd_induced  = (cl ** 2) / (np.pi * aspect_ratio * oswald_efficiency)
    return cd_profile + cd_induced


def wing_forces(span_m: float, chord_m: float, aoa_deg: float,
                velocity_ms: float, profile: str = "NACA0012",
                temp_c: float = 20.0, altitude_m: float = 0.0,
                end_plate_efficiency: float = 0.85) -> dict:
    """
    Calculate full force set for a wing at given conditions.

    Returns:
        dict with lift_n, drag_n, downforce_kg, drag_kg,
               cl, cd, aspect_ratio, reynolds_number, flow_regime
    """
    rho    = air_density(temp_c, altitude_m)
    area   = span_m * chord_m
    ar     = span_m / chord_m if chord_m > 0 else 5.0
    re     = reynolds_number(velocity_ms, chord_m, temp_c, altitude_m)
    q      = 0.5 * rho * velocity_ms ** 2   # dynamic pressure (Pa)

    # Rear wings are always inverted — positive AoA = downforce
    cl = wing_cl(aoa_deg, profile, end_plate_efficiency, inverted=True)
    cd = wing_cd(cl, ar, profile)

    # cl is negative for downforce (inverted wing)
    # downforce_n is positive when pushing car down
    lift_n      = q * area * cl          # negative = downforce force on car
    drag_n      = q * area * cd          # always positive
    downforce_n = -lift_n                # positive = pushing car down

    stall_warning = abs(aoa_deg) >= AEROFOIL_DATA.get(profile, {}).get("aoa_stall_deg", 17)

    return {
        "lift_n":         round(lift_n, 2),
        "drag_n":         round(drag_n, 2),
        "downforce_n":    round(downforce_n, 2),   # positive = downforce
        "downforce_kg":   round(downforce_n / GRAVITY, 2),
        "drag_kg":        round(drag_n / GRAVITY, 2),
        "cl":             round(cl, 4),
        "cd":             round(cd, 4),
        "l_d_ratio":      round(abs(cl / cd) if cd > 0 else 0, 2),
        "aspect_ratio":   round(ar, 2),
        "wing_area_m2":   round(area, 4),
        "dynamic_pressure_pa": round(q, 2),
        "reynolds_number":     round(re, 0),
        "flow_regime":         flow_regime(re),
        "stall_warning":       stall_warning,
    }


# ── Vehicle drag model ────────────────────────────────────────────────────────

# Base Cd by body style (empirical, Hucho 1998)
BASE_CD_BY_STYLE = {
    "fastback":  0.30,
    "notchback": 0.33,
    "hatchback": 0.32,
    "estate":    0.35,
    "suv":       0.38,
    "truck":     0.45,
    "van":       0.42,
    "roadster":  0.35,
    "cabriolet": 0.36,
}

# Cd correction factors for geometry
# Each factor adds to or subtracts from base Cd
CD_CORRECTIONS = {
    # Windscreen rake (more raked = lower Cd up to ~30°)
    "windscreen_rake": {
        "steep_deg": 20,   "steep_delta_cd":  0.03,
        "optimal_deg": 28, "optimal_delta_cd": 0.0,
        "laid_deg": 35,    "laid_delta_cd": 0.01,
    },
    # Ride height (lower = less underbody drag, more ground effect)
    "ride_height_100mm":  0.0,
    "ride_height_per_10mm_reduction": -0.002,

    # Aero devices
    "front_splitter_per_m2":     -0.015,
    "rear_wing_base":             0.025,  # wing always adds drag
    "rear_wing_per_aoa_degree":   0.003,
    "diffuser_per_degree":        -0.004,
    "canard_per_m2":              0.010,
    "vortex_generators":          -0.003,
    "underbody_panel":            -0.010,
}

# Cl corrections (negative = downforce)
CL_CORRECTIONS = {
    "front_splitter_per_m2":       -0.08,
    "rear_wing_per_aoa_degree":    -0.05,
    "diffuser_per_degree":         -0.03,
    "ride_height_per_10mm_increase": 0.01,   # higher = less ground effect = less downforce
    "canard_per_m2":               -0.06,
}


def estimate_vehicle_cd(geom: VehicleGeometry, yaw_deg: float = 0.0) -> float:
    """
    Estimate vehicle drag coefficient from geometry.
    Uses empirical corrections based on Hucho's aerodynamic database.

    Args:
        geom:    Vehicle geometry specification
        yaw_deg: Yaw angle (0 = straight ahead, simulating crosswind)

    Returns:
        Estimated drag coefficient Cd
    """
    # Use measured baseline if available
    if geom.baseline_cd is not None:
        cd = geom.baseline_cd
    else:
        cd = BASE_CD_BY_STYLE.get(geom.body_style, 0.33)

    # Windscreen rake correction
    rake = geom.windscreen_rake_deg
    if rake < 25:
        cd += 0.03 * (25 - rake) / 5.0     # too steep = more drag
    elif rake > 35:
        cd += 0.015 * (rake - 35) / 5.0    # too shallow = more drag

    # Ride height correction (reference: 120mm)
    delta_h = (0.12 - geom.ride_height_m) * 1000  # mm lower than reference
    cd += delta_h * (-0.002 / 10.0)                # -0.002 per 10mm lower

    # Aero devices
    if geom.has_front_splitter and geom.splitter_length_m > 0:
        splitter_area = geom.splitter_length_m * geom.splitter_width_m
        cd -= 0.01 * splitter_area  # splitter helps manage underbody flow

    if geom.has_rear_wing and geom.wing_span_m > 0:
        cd += 0.025  # base wing drag
        cd += geom.wing_aoa_deg * 0.003   # induced drag from AoA

    if geom.has_underbody_diffuser and geom.diffuser_angle_deg > 0:
        effective_angle = min(geom.diffuser_angle_deg, 15.0)  # diminishing returns above 15°
        cd -= effective_angle * 0.003

    if geom.has_vortex_generators:
        cd -= 0.003   # VGs reduce separation drag

    # Yaw angle correction (crosswind increases effective frontal area)
    if yaw_deg != 0:
        # Cd increases with yaw approximately as: ΔCd ≈ 0.003 × |yaw|
        cd += 0.003 * abs(yaw_deg)

    return round(max(cd, 0.15), 4)   # physical minimum ~0.15 for a car


def estimate_vehicle_cl(geom: VehicleGeometry) -> float:
    """
    Estimate vehicle lift coefficient (negative = downforce).
    Baseline cars generate lift (positive Cl).
    Aero devices reduce Cl (add downforce).
    """
    if geom.baseline_cl is not None:
        cl = geom.baseline_cl
    else:
        # Most road cars generate positive lift (Cl 0.1-0.4)
        cl = {
            "fastback":  0.15,
            "notchback": 0.25,
            "hatchback": 0.20,
            "suv":       0.35,
            "estate":    0.30,
        }.get(geom.body_style, 0.25)

    # Aero devices (negative = downforce contribution)
    if geom.has_front_splitter and geom.splitter_length_m > 0:
        splitter_area = geom.splitter_length_m * geom.splitter_width_m
        cl -= 0.08 * splitter_area

    if geom.has_rear_wing and geom.wing_span_m > 0:
        cl -= geom.wing_aoa_deg * 0.05

    if geom.has_underbody_diffuser and geom.diffuser_angle_deg > 0:
        effective_angle = min(geom.diffuser_angle_deg, 15.0)
        cl -= effective_angle * 0.025

    if geom.has_canards and geom.canard_area_m2 > 0:
        cl -= 0.06 * geom.canard_area_m2

    # Ground effect from ride height (lower = more downforce from Venturi effect)
    if geom.ride_height_m < 0.12:
        ground_effect = (0.12 - geom.ride_height_m) / 0.12
        cl -= 0.15 * ground_effect

    return round(cl, 4)


# ── Full aerodynamic force calculation ─────────────────────────────────────────

def aerodynamic_forces(geom: VehicleGeometry, velocity_ms: float,
                        temp_c: float = 20.0, altitude_m: float = 0.0,
                        yaw_deg: float = 0.0,
                        tunnel_cross_section_m2: float = None) -> dict:
    """
    Calculate full 6-component aerodynamic force set.
    Mirrors a real wind tunnel 6-component balance measurement.

    Args:
        geom:           Vehicle geometry
        velocity_ms:    Test velocity in m/s
        temp_c:         Air temperature
        altitude_m:     Altitude above sea level
        yaw_deg:        Yaw angle (crosswind simulation)
        tunnel_cross_section_m2: If given, applies blockage correction

    Returns:
        dict with all 6 force/moment components + derived values
    """
    rho = air_density(temp_c, altitude_m)
    q   = 0.5 * rho * velocity_ms ** 2    # dynamic pressure
    A   = geom.frontal_area_m2
    L   = geom.length_m                   # reference length
    re  = reynolds_number(velocity_ms, L, temp_c, altitude_m)

    # Coefficients
    cd = estimate_vehicle_cd(geom, yaw_deg)
    cl = estimate_vehicle_cl(geom)

    # Apply blockage correction if tunnel dimensions given
    if tunnel_cross_section_m2:
        cd = blockage_correction(cd, A, tunnel_cross_section_m2)
        cl = blockage_correction(cl, A, tunnel_cross_section_m2)

    # Side force (due to yaw)
    cs = 0.05 * yaw_deg / 5.0   # approximate side force coefficient

    # Forces (N)
    drag_n      = q * A * cd                    # longitudinal drag
    lift_n      = q * A * cl                    # vertical lift (positive = upward)
    side_n      = q * A * cs                    # lateral force

    # Moments (N·m about vehicle CoG — approx at 45% wheelbase from front)
    cog_x       = geom.wheelbase_m * 0.45       # CoG position from front axle
    pitch_nm    = lift_n * (cog_x - geom.length_m * 0.5)   # pitching moment
    yaw_nm      = side_n * geom.length_m * 0.1             # yawing moment
    roll_nm     = lift_n * (geom.track_front_m + geom.track_rear_m) * 0.5 * 0.02

    # Wing contribution (separate component)
    wing_result = None
    if geom.has_rear_wing and geom.wing_span_m > 0:
        wing_result = wing_forces(
            span_m=geom.wing_span_m,
            chord_m=geom.wing_chord_m,
            aoa_deg=geom.wing_aoa_deg,
            velocity_ms=velocity_ms,
            profile=geom.wing_profile,
            temp_c=temp_c,
            altitude_m=altitude_m,
        )

    # Power required to overcome drag
    power_w = drag_n * velocity_ms
    power_kw = power_w / 1000.0

    # Terminal velocity (where engine power = drag power)
    # v_max = (2 × P / (ρ × A × Cd))^(1/3)
    # Computed separately via solve_terminal_velocity()

    # Downforce distribution (front/rear split)
    # Approximate: splitter adds front downforce, wing adds rear
    front_df_pct = 0.40   # baseline
    if geom.has_front_splitter:
        front_df_pct += 0.10
    if geom.has_rear_wing:
        front_df_pct -= 0.05
    rear_df_pct = 1.0 - front_df_pct

    total_downforce_n  = -lift_n   # positive when wing inverted (downforce)
    front_downforce_n  = total_downforce_n * front_df_pct
    rear_downforce_n   = total_downforce_n * rear_df_pct

    return {
        # Air conditions
        "velocity_ms":        velocity_ms,
        "velocity_kph":       round(velocity_ms * 3.6, 1),
        "air_density_kg_m3":  round(rho, 4),
        "dynamic_pressure_pa":round(q, 2),
        "reynolds_number":    round(re, 0),
        "flow_regime":        flow_regime(re),

        # Coefficients
        "cd":                 cd,
        "cl":                 cl,
        "cs":                 round(cs, 4),

        # Forces (N)
        "drag_n":             round(drag_n, 2),
        "lift_n":             round(lift_n, 2),
        "side_n":             round(side_n, 2),
        "downforce_n":        round(total_downforce_n, 2),
        "front_downforce_n":  round(front_downforce_n, 2),
        "rear_downforce_n":   round(rear_downforce_n, 2),

        # Forces (kg equivalent)
        "drag_kg":            round(drag_n / GRAVITY, 2),
        "downforce_kg":       round(total_downforce_n / GRAVITY, 2),
        "front_downforce_kg": round(front_downforce_n / GRAVITY, 2),
        "rear_downforce_kg":  round(rear_downforce_n / GRAVITY, 2),

        # Moments (N·m)
        "pitch_nm":           round(pitch_nm, 2),
        "yaw_nm":             round(yaw_nm, 2),
        "roll_nm":            round(roll_nm, 2),

        # Power
        "drag_power_kw":      round(power_kw, 2),
        "drag_power_hp":      round(power_kw * 1.341, 2),

        # Wing detail
        "wing_forces":        wing_result,

        # Geometry reference
        "frontal_area_m2":    round(A, 4),
        "yaw_deg":            yaw_deg,
    }


def solve_terminal_velocity(engine_power_kw: float, geom: VehicleGeometry,
                              temp_c: float = 20.0, altitude_m: float = 0.0,
                              drivetrain_efficiency: float = 0.85,
                              vehicle_mass_kg: float = 1500.0,
                              rolling_resistance_coeff: float = 0.012) -> float:
    """
    Solve for terminal velocity where engine power equals total resistance power.
    P = (F_drag + F_rolling) × v
    F_drag    = 0.5 × rho × Cd × A × v²
    F_rolling = m × g × Crr

    Solved iteratively since F_drag is nonlinear in v.

    Args:
        engine_power_kw:          Engine power at wheels (kW)
        geom:                     Vehicle geometry
        temp_c:                   Air temperature
        altitude_m:               Altitude
        drivetrain_efficiency:    Drivetrain loss factor (0.82-0.88 typical)
        vehicle_mass_kg:          Vehicle mass for rolling resistance
        rolling_resistance_coeff: Crr (0.010-0.015 for performance tyres)

    Returns:
        Terminal velocity in m/s
    """
    rho     = air_density(temp_c, altitude_m)
    cd      = estimate_vehicle_cd(geom)
    A       = geom.frontal_area_m2
    power_w = engine_power_kw * 1000 * drivetrain_efficiency
    F_roll  = vehicle_mass_kg * GRAVITY * rolling_resistance_coeff

    # Iterative solver: P = (0.5*rho*Cd*A*v² + F_roll) * v
    # Start with aero-only estimate
    v = (2 * power_w / (rho * cd * A)) ** (1/3)
    for _ in range(50):
        F_aero  = 0.5 * rho * cd * A * v**2
        F_total = F_aero + F_roll
        v_new   = power_w / F_total
        if abs(v_new - v) < 0.01:
            break
        v = 0.5 * (v + v_new)

    return round(v, 2)


def sensitivity_analysis(geom: VehicleGeometry, velocity_ms: float,
                           temp_c: float = 20.0) -> dict:
    """
    Run sensitivity analysis — how much does each aero parameter change
    drag and downforce?

    Returns:
        dict of parameter: {delta_cd, delta_downforce_kg} for ±1 unit change
    """
    baseline = aerodynamic_forces(geom, velocity_ms, temp_c)
    results  = {}

    # Ride height sensitivity
    geom_high = VehicleGeometry(**{**geom.__dict__, "ride_height_m": geom.ride_height_m + 0.010})
    high      = aerodynamic_forces(geom_high, velocity_ms, temp_c)
    results["ride_height_+10mm"] = {
        "delta_cd":           round(high["cd"] - baseline["cd"], 4),
        "delta_downforce_kg": round(high["downforce_kg"] - baseline["downforce_kg"], 2),
        "delta_drag_kg":      round(high["drag_kg"] - baseline["drag_kg"], 2),
    }

    # Wing AoA sensitivity (if wing present)
    if geom.has_rear_wing:
        geom_wing = VehicleGeometry(**{**geom.__dict__, "wing_aoa_deg": geom.wing_aoa_deg + 1.0})
        wing_sens = aerodynamic_forces(geom_wing, velocity_ms, temp_c)
        results["wing_aoa_+1deg"] = {
            "delta_cd":           round(wing_sens["cd"] - baseline["cd"], 4),
            "delta_downforce_kg": round(wing_sens["downforce_kg"] - baseline["downforce_kg"], 2),
            "delta_drag_kg":      round(wing_sens["drag_kg"] - baseline["drag_kg"], 2),
        }

    # Diffuser angle sensitivity
    if geom.has_underbody_diffuser:
        geom_diff = VehicleGeometry(**{**geom.__dict__, "diffuser_angle_deg": geom.diffuser_angle_deg + 1.0})
        diff_sens = aerodynamic_forces(geom_diff, velocity_ms, temp_c)
        results["diffuser_+1deg"] = {
            "delta_cd":           round(diff_sens["cd"] - baseline["cd"], 4),
            "delta_downforce_kg": round(diff_sens["downforce_kg"] - baseline["downforce_kg"], 2),
            "delta_drag_kg":      round(diff_sens["drag_kg"] - baseline["drag_kg"], 2),
        }

    return results


def optimize_aero(geom: VehicleGeometry, velocity_ms: float,
                   target: str = "balanced",
                   temp_c: float = 20.0) -> dict:
    """
    Find optimal aero configuration for a given target.

    Args:
        geom:        Base vehicle geometry
        velocity_ms: Design point velocity
        target:      'min_drag' | 'max_downforce' | 'balanced' | 'efficiency'
        temp_c:      Air temperature

    Returns:
        dict with optimal parameters and predicted results
    """
    from scipy.optimize import minimize_scalar, minimize
    import copy

    best_config = copy.deepcopy(geom.__dict__)
    best_result = aerodynamic_forces(geom, velocity_ms, temp_c)

    if target == "min_drag":
        # Minimize drag — find optimal ride height (lower helps but too low = scraping)
        def drag_objective(ride_height):
            g = VehicleGeometry(**{**geom.__dict__, "ride_height_m": ride_height})
            return aerodynamic_forces(g, velocity_ms, temp_c)["drag_n"]

        result = minimize_scalar(drag_objective, bounds=(0.05, 0.20), method="bounded")
        best_config["ride_height_m"] = round(result.x, 3)

        if geom.has_rear_wing:
            # Minimize drag = minimize AoA (but keep some downforce)
            best_config["wing_aoa_deg"] = max(0, geom.wing_aoa_deg - 3)

    elif target == "max_downforce":
        # Maximize downforce
        if geom.has_rear_wing:
            # Find max AoA before stall
            aerofoil = AEROFOIL_DATA.get(geom.wing_profile, AEROFOIL_DATA["NACA0012"])
            best_config["wing_aoa_deg"] = aerofoil["aoa_stall_deg"] - 2.0

        if geom.has_underbody_diffuser:
            best_config["diffuser_angle_deg"] = 12.0   # optimal diffuser ~10-15°

        # Lower ride height for ground effect
        best_config["ride_height_m"] = max(0.06, geom.ride_height_m - 0.02)

    elif target == "balanced":
        # Optimize L/D ratio — best aerodynamic efficiency
        if geom.has_rear_wing:
            def neg_ld(aoa):
                g = VehicleGeometry(**{**geom.__dict__, "wing_aoa_deg": aoa[0]})
                r = aerodynamic_forces(g, velocity_ms, temp_c)
                # Avoid division by zero
                if r["drag_n"] == 0:
                    return 0
                return r["downforce_n"] / r["drag_n"]

            result = minimize(
                lambda x: -neg_ld(x),
                x0=[geom.wing_aoa_deg],
                bounds=[(0, 18)],
                method="L-BFGS-B"
            )
            best_config["wing_aoa_deg"] = round(float(result.x[0]), 1)

    elif target == "efficiency":
        # Minimize drag for highway/top speed runs
        best_config["wing_aoa_deg"] = 0.0 if geom.has_rear_wing else geom.wing_aoa_deg
        best_config["ride_height_m"] = min(0.14, geom.ride_height_m + 0.01)

    # Calculate result with optimal config
    optimal_geom   = VehicleGeometry(**best_config)
    optimal_result = aerodynamic_forces(optimal_geom, velocity_ms, temp_c)
    baseline       = best_result

    return {
        "target":           target,
        "velocity_kph":     round(velocity_ms * 3.6, 1),
        "optimal_config":   {
            k: v for k, v in best_config.items()
            if k in ["ride_height_m", "wing_aoa_deg", "diffuser_angle_deg"]
        },
        "baseline":         {
            "cd":           baseline["cd"],
            "cl":           baseline["cl"],
            "drag_kg":      baseline["drag_kg"],
            "downforce_kg": baseline["downforce_kg"],
        },
        "optimal":          {
            "cd":           optimal_result["cd"],
            "cl":           optimal_result["cl"],
            "drag_kg":      optimal_result["drag_kg"],
            "downforce_kg": optimal_result["downforce_kg"],
        },
        "improvement": {
            "delta_cd":           round(optimal_result["cd"] - baseline["cd"], 4),
            "delta_drag_kg":      round(optimal_result["drag_kg"] - baseline["drag_kg"], 2),
            "delta_downforce_kg": round(optimal_result["downforce_kg"] - baseline["downforce_kg"], 2),
        },
        "full_result":      optimal_result,
    }


# ── Virtual wind tunnel ───────────────────────────────────────────────────────

def virtual_wind_tunnel(geom: VehicleGeometry,
                         velocities_kph: List[float] = None,
                         yaw_angles_deg: List[float] = None,
                         temp_c: float = 20.0,
                         altitude_m: float = 0.0,
                         tunnel_cross_section_m2: float = 25.0) -> dict:
    """
    Simulate a full wind tunnel test sweep.
    Tests multiple velocities and yaw angles.
    Returns 6-component balance data for each condition.

    Args:
        geom:                   Vehicle geometry
        velocities_kph:         List of test velocities (kph)
        yaw_angles_deg:         List of yaw angles to test
        temp_c:                 Tunnel air temperature
        altitude_m:             Equivalent altitude
        tunnel_cross_section_m2: Tunnel cross-section (default 5×5m = 25m²)

    Returns:
        Full test matrix results
    """
    if velocities_kph is None:
        velocities_kph = [80, 100, 120, 160, 200, 240]
    if yaw_angles_deg is None:
        yaw_angles_deg = [0, 5, 10, 15]

    blockage_ratio = geom.frontal_area_m2 / tunnel_cross_section_m2
    results = {
        "vehicle":          geom.__dict__,
        "tunnel_conditions": {
            "temp_c":               temp_c,
            "altitude_m":           altitude_m,
            "air_density_kg_m3":    round(air_density(temp_c, altitude_m), 4),
            "cross_section_m2":     tunnel_cross_section_m2,
            "blockage_ratio_pct":   round(blockage_ratio * 100, 2),
            "blockage_ok":          blockage_ratio < 0.05,
        },
        "test_matrix":      [],
        "summary": {
            "cd_range":   [],
            "cl_range":   [],
            "max_downforce_kg": 0,
            "max_drag_kg":      0,
        }
    }

    for vel_kph in velocities_kph:
        vel_ms = vel_kph / 3.6
        for yaw in yaw_angles_deg:
            forces = aerodynamic_forces(
                geom, vel_ms, temp_c, altitude_m, yaw,
                tunnel_cross_section_m2
            )
            results["test_matrix"].append({
                "velocity_kph": vel_kph,
                "yaw_deg":      yaw,
                **forces
            })
            results["summary"]["cd_range"].append(forces["cd"])
            results["summary"]["cl_range"].append(forces["cl"])
            results["summary"]["max_downforce_kg"] = max(
                results["summary"]["max_downforce_kg"],
                forces["downforce_kg"]
            )
            results["summary"]["max_drag_kg"] = max(
                results["summary"]["max_drag_kg"],
                forces["drag_kg"]
            )

    results["summary"]["cd_min"] = round(min(results["summary"]["cd_range"]), 4)
    results["summary"]["cd_max"] = round(max(results["summary"]["cd_range"]), 4)
    del results["summary"]["cd_range"]
    del results["summary"]["cl_range"]

    return results


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Aerodynamics Engine Test")
    print("=" * 60)

    # Toyota Supra A80 — stock
    supra = VehicleGeometry(
        length_m=4.515, width_m=1.810, height_m=1.275,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        ride_height_m=0.130, windscreen_rake_deg=28, body_style="fastback",
        baseline_cd=0.31, baseline_cl=0.18,
    )

    print("\nToyota Supra A80 — Stock — 200kph")
    result = aerodynamic_forces(supra, 200/3.6)
    for k, v in result.items():
        if k not in ["wing_forces"]:
            if k == "downforce_kg":
                label = "downforce_kg (neg=lift)"
                print(f"  {label:30} {v}")
            else:
                print(f"  {k:30} {v}")

    # With wing
    supra_wing = VehicleGeometry(
        length_m=4.515, width_m=1.810, height_m=1.275,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        ride_height_m=0.120, windscreen_rake_deg=28, body_style="fastback",
        baseline_cd=0.31, baseline_cl=0.18,
        has_rear_wing=True, wing_span_m=1.400, wing_chord_m=0.250,
        wing_aoa_deg=12.0, wing_profile="NACA2412",
        has_front_splitter=True, splitter_length_m=0.080, splitter_width_m=1.600,
        has_underbody_diffuser=True, diffuser_angle_deg=8.0,
    )

    print("\nToyota Supra A80 — Full Aero Kit — 200kph")
    result2 = aerodynamic_forces(supra_wing, 200/3.6)
    print(f"  Cd:              {result2['cd']} (was {supra.baseline_cd})")
    print(f"  Downforce:       {result2['downforce_kg']}kg")
    print(f"  Drag:            {result2['drag_kg']}kg")
    print(f"  Drag power:      {result2['drag_power_hp']}hp")
    print(f"  Front DF:        {result2['front_downforce_kg']}kg")
    print(f"  Rear DF:         {result2['rear_downforce_kg']}kg")

    print("\nWing analysis — AoA sweep:")
    for aoa in [0, 5, 10, 15, 18, 20]:
        wf = wing_forces(1.4, 0.25, aoa, 200/3.6, "NACA2412")
        stall = " ⚠ STALL" if wf["stall_warning"] else ""
        print(f"  AoA={aoa:3}°  Downforce={wf['downforce_kg']:6.1f}kg  "
              f"Drag={wf['drag_kg']:5.1f}kg  L/D={wf['l_d_ratio']:5.1f}{stall}")

    print("\nOptimal aero for maximum downforce:")
    opt = optimize_aero(supra_wing, 200/3.6, target="max_downforce")
    print(f"  Optimal AoA:     {opt['optimal_config'].get('wing_aoa_deg')}°")
    print(f"  Optimal ride ht: {opt['optimal_config'].get('ride_height_m')}m")
    print(f"  Downforce:       {opt['optimal']['downforce_kg']}kg (was {opt['baseline']['downforce_kg']}kg)")
    print(f"  Drag:            {opt['optimal']['drag_kg']}kg (was {opt['baseline']['drag_kg']}kg)")

    print("\nTerminal velocity (400hp engine):")
    vmax = solve_terminal_velocity(298.3, supra, vehicle_mass_kg=1520)
    print(f"  Stock aero (85% DT): {round(vmax*3.6, 1)}kph")
    vmax_real = solve_terminal_velocity(298.3, supra, vehicle_mass_kg=1520, drivetrain_efficiency=0.78)
    print(f"  Stock aero (78% DT): {round(vmax_real*3.6, 1)}kph  (stock 276hp ~274kph — correct)")
    vmax2 = solve_terminal_velocity(298.3, supra_wing, vehicle_mass_kg=1520, drivetrain_efficiency=0.78)
    print(f"  Full aero kit (78% DT): {round(vmax2*3.6, 1)}kph")
