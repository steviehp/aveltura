"""
physics_engine/tyre_model.py — Tyre Mechanics and Grip Model

Implements:
  1. Pacejka Magic Formula (simplified 3-parameter version)
     - Lateral force (cornering)
     - Longitudinal force (braking/acceleration)
     - Combined slip (simultaneous cornering + braking)

  2. Thermal model
     - Tyre surface and core temperature
     - Heat generation from slip
     - Heat dissipation to road and air
     - Grip vs temperature curve

  3. Load sensitivity
     - Grip degrades as vertical load increases (tyre nonlinearity)
     - Critical for understanding weight transfer effects

  4. Contact patch model
     - Contact patch size from load, pressure, tyre dimensions
     - Pressure distribution across patch

References:
  - Pacejka, H.B. "Tyre and Vehicle Dynamics" (3rd ed.)
  - Milliken & Milliken "Race Car Vehicle Dynamics"
  - Kistler "Tyre Measurement Technology"

Coordinate system: ISO 8855
  X = longitudinal (forward)
  Y = lateral (left)
  Z = vertical (up)
  Slip angle α = angle between wheel heading and velocity vector
  Slip ratio κ = (ω×r - v) / v (positive = driving, negative = braking)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, List
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from materials_db import TyreCompound, TYRE_COMPOUNDS

GRAVITY = 9.81   # m/s²


# ── Tyre geometry ─────────────────────────────────────────────────────────────

@dataclass
class TyreGeometry:
    """
    Tyre dimensional specification.
    Standard notation: 265/35R19
      width_mm = 265
      aspect_ratio = 35 (sidewall height as % of width)
      rim_diameter_in = 19
    """
    width_mm:           float    # section width (mm)
    aspect_ratio_pct:   float    # sidewall height as % of width
    rim_diameter_in:    float    # rim diameter (inches)
    inflation_kpa:      float = 220.0   # inflation pressure (kPa)

    @property
    def sidewall_height_mm(self) -> float:
        return self.width_mm * self.aspect_ratio_pct / 100.0

    @property
    def overall_diameter_mm(self) -> float:
        return self.rim_diameter_in * 25.4 + 2 * self.sidewall_height_mm

    @property
    def overall_radius_m(self) -> float:
        return self.overall_diameter_mm / 2000.0

    @property
    def loaded_radius_m(self) -> float:
        """Approximate loaded radius (under load, tyre squishes ~2-3%)."""
        return self.overall_radius_m * 0.975

    @property
    def contact_width_m(self) -> float:
        """Approximate contact patch width (~85% of section width)."""
        return self.width_mm * 0.85 / 1000.0

    def contact_patch_area_m2(self, vertical_load_n: float) -> float:
        """
        Estimate contact patch area from vertical load and inflation pressure.
        F_z = p × A  →  A = F_z / p
        (simplified — ignores carcass stiffness)
        """
        pressure_pa = self.inflation_kpa * 1000.0
        area = vertical_load_n / pressure_pa
        return max(area, 0.005)   # minimum 50cm²

    def contact_patch_length_m(self, vertical_load_n: float) -> float:
        """Contact patch length from area and width."""
        area  = self.contact_patch_area_m2(vertical_load_n)
        width = self.contact_width_m
        return area / width if width > 0 else 0.0

    def summary(self) -> dict:
        return {
            "size":               f"{int(self.width_mm)}/{int(self.aspect_ratio_pct)}R{int(self.rim_diameter_in)}",
            "overall_diameter_mm":round(self.overall_diameter_mm, 1),
            "loaded_radius_m":    round(self.loaded_radius_m, 4),
            "contact_width_m":    round(self.contact_width_m, 4),
            "inflation_kpa":      self.inflation_kpa,
        }


# ── Pacejka Magic Formula ─────────────────────────────────────────────────────

@dataclass
class PacejkaCoefficients:
    """
    Pacejka Magic Formula coefficients for a specific tyre.
    Simplified 3-parameter form: F = D × sin(C × arctan(B×x - E×(B×x - arctan(B×x))))
    where x = slip angle (lateral) or slip ratio (longitudinal).

    B = stiffness factor
    C = shape factor
    D = peak value
    E = curvature factor
    """
    # Lateral (cornering) coefficients
    B_lat:  float = 10.0    # stiffness factor
    C_lat:  float = 1.30    # shape factor (1.3 = lateral typical)
    D_lat:  float = 1.0     # peak friction coefficient (at reference load)
    E_lat:  float = -1.0    # curvature factor

    # Longitudinal (braking/driving) coefficients
    B_lon:  float = 12.0
    C_lon:  float = 1.60    # shape factor (1.6 = longitudinal typical)
    D_lon:  float = 1.0
    E_lon:  float = -0.5

    # Load sensitivity — grip reduces as load increases
    # μ = μ_ref × (1 - q_Bz × (Fz/Fz_ref - 1))
    load_sensitivity:   float = 0.15   # q_Bz — 0.1-0.2 typical
    reference_load_n:   float = 3000.0 # reference vertical load (N)

    # Camber sensitivity (degrees)
    camber_sensitivity: float = 0.05   # ΔD per degree camber

    @classmethod
    def from_compound(cls, compound_name: str) -> "PacejkaCoefficients":
        """Create coefficients from tyre compound name."""
        compound_presets = {
            "slick_soft": cls(
                B_lat=12.0, C_lat=1.40, D_lat=1.60, E_lat=-1.5,
                B_lon=14.0, C_lon=1.70, D_lon=1.60, E_lon=-0.8,
                load_sensitivity=0.10,
            ),
            "slick_medium": cls(
                B_lat=11.0, C_lat=1.35, D_lat=1.50, E_lat=-1.2,
                B_lon=13.0, C_lon=1.65, D_lon=1.50, E_lon=-0.6,
                load_sensitivity=0.12,
            ),
            "semi_slick": cls(
                B_lat=10.0, C_lat=1.30, D_lat=1.35, E_lat=-1.0,
                B_lon=12.0, C_lon=1.60, D_lon=1.35, E_lon=-0.5,
                load_sensitivity=0.13,
            ),
            "performance_street": cls(
                B_lat=9.0,  C_lat=1.25, D_lat=1.15, E_lat=-0.8,
                B_lon=11.0, C_lon=1.55, D_lon=1.15, E_lon=-0.4,
                load_sensitivity=0.15,
            ),
            "standard_street": cls(
                B_lat=8.0,  C_lat=1.20, D_lat=0.95, E_lat=-0.5,
                B_lon=10.0, C_lon=1.50, D_lon=0.95, E_lon=-0.3,
                load_sensitivity=0.18,
            ),
        }
        return compound_presets.get(compound_name, cls())


def magic_formula(x: float, B: float, C: float, D: float, E: float) -> float:
    """
    Pacejka Magic Formula:
    F = D × sin(C × arctan(B×x - E×(B×x - arctan(B×x))))

    Args:
        x: Input (slip angle in rad or slip ratio dimensionless)
        B, C, D, E: Pacejka coefficients

    Returns:
        Force coefficient (μ)
    """
    BEx = B * x
    return D * np.sin(C * np.arctan(BEx - E * (BEx - np.arctan(BEx))))


def lateral_force_coefficient(slip_angle_deg: float, coeffs: PacejkaCoefficients,
                               vertical_load_n: float,
                               camber_deg: float = 0.0,
                               temp_factor: float = 1.0) -> float:
    """
    Calculate lateral friction coefficient (μ_y) from slip angle.

    Args:
        slip_angle_deg:  Tyre slip angle in degrees
        coeffs:          Pacejka coefficients
        vertical_load_n: Vertical tyre load (N)
        camber_deg:      Camber angle (negative = top of tyre leaning in)
        temp_factor:     Grip multiplier from temperature model (0-1.2)

    Returns:
        Lateral friction coefficient μ_y
    """
    # Convert to radians for Magic Formula
    alpha_rad = np.radians(slip_angle_deg)

    # Load sensitivity — peak grip reduces at higher loads
    load_ratio = vertical_load_n / coeffs.reference_load_n
    D_adj = coeffs.D_lat * (1 - coeffs.load_sensitivity * (load_ratio - 1))
    D_adj = max(D_adj, 0.3)  # physical minimum

    # Camber contribution (negative camber increases lateral grip slightly)
    D_adj += coeffs.camber_sensitivity * abs(min(camber_deg, 0))

    # Magic Formula
    mu_y = magic_formula(alpha_rad, coeffs.B_lat, coeffs.C_lat, D_adj, coeffs.E_lat)

    return mu_y * temp_factor


def longitudinal_force_coefficient(slip_ratio: float, coeffs: PacejkaCoefficients,
                                    vertical_load_n: float,
                                    temp_factor: float = 1.0) -> float:
    """
    Calculate longitudinal friction coefficient (μ_x) from slip ratio.
    Positive slip ratio = driving (wheelspin)
    Negative slip ratio = braking (lockup)

    Args:
        slip_ratio:      Dimensionless (-1.0 to 1.0)
        coeffs:          Pacejka coefficients
        vertical_load_n: Vertical tyre load (N)
        temp_factor:     Grip multiplier from temperature model

    Returns:
        Longitudinal friction coefficient μ_x
    """
    load_ratio = vertical_load_n / coeffs.reference_load_n
    D_adj = coeffs.D_lon * (1 - coeffs.load_sensitivity * (load_ratio - 1))
    D_adj = max(D_adj, 0.3)

    mu_x = magic_formula(slip_ratio, coeffs.B_lon, coeffs.C_lon, D_adj, coeffs.E_lon)
    return mu_x * temp_factor


def combined_slip(slip_angle_deg: float, slip_ratio: float,
                   coeffs: PacejkaCoefficients, vertical_load_n: float,
                   temp_factor: float = 1.0) -> Tuple[float, float]:
    """
    Combined slip — simultaneous lateral and longitudinal forces.
    Uses friction ellipse (Kamm circle) approximation.

    The friction ellipse states:
    (Fx/Fx_max)² + (Fy/Fy_max)² ≤ 1

    Returns:
        (mu_x_combined, mu_y_combined)
    """
    mu_x_pure = longitudinal_force_coefficient(slip_ratio, coeffs, vertical_load_n, temp_factor)
    mu_y_pure = lateral_force_coefficient(slip_angle_deg, coeffs, vertical_load_n, 0, temp_factor)

    # Scaling factors from combined slip theory
    if abs(mu_x_pure) + abs(mu_y_pure) < 1e-6:
        return 0.0, 0.0

    # Resultant limited by friction circle
    resultant = np.sqrt(mu_x_pure**2 + mu_y_pure**2)

    # Peak combined friction (slightly less than pure)
    mu_peak = max(abs(mu_x_pure), abs(mu_y_pure)) * 1.05

    if resultant > mu_peak:
        scale = mu_peak / resultant
        return mu_x_pure * scale, mu_y_pure * scale

    return mu_x_pure, mu_y_pure


def grip_circle(coeffs: PacejkaCoefficients, vertical_load_n: float,
                 n_points: int = 72, temp_factor: float = 1.0) -> dict:
    """
    Generate the complete friction/grip circle.
    Shows maximum combined force envelope.

    Returns:
        dict with x_values, y_values for plotting + key metrics
    """
    angles = np.linspace(0, 2*np.pi, n_points)
    slip_ratios   = np.sin(angles) * 0.3  # max slip ratio ±0.3
    slip_angles   = np.degrees(np.cos(angles)) * 12.0  # max slip angle ±12°

    mu_x_vals = []
    mu_y_vals = []

    for sr, sa in zip(slip_ratios, slip_angles):
        mx, my = combined_slip(sa, sr, coeffs, vertical_load_n, temp_factor)
        mu_x_vals.append(mx)
        mu_y_vals.append(my)

    return {
        "mu_x":         mu_x_vals,
        "mu_y":         mu_y_vals,
        "peak_lateral": round(max(abs(v) for v in mu_y_vals), 3),
        "peak_longitudinal": round(max(abs(v) for v in mu_x_vals), 3),
        "peak_combined":round(max(np.sqrt(x**2 + y**2) for x, y in
                                   zip(mu_x_vals, mu_y_vals)), 3),
    }


# ── Thermal model ─────────────────────────────────────────────────────────────

@dataclass
class TyreThermalState:
    """Current thermal state of a tyre."""
    surface_temp_c: float = 20.0   # rubber surface temperature
    core_temp_c:    float = 20.0   # tyre core/carcass temperature
    ambient_temp_c: float = 20.0   # ambient air temperature
    road_temp_c:    float = 30.0   # road surface temperature


def grip_from_temperature(temp_c: float, compound: TyreCompound) -> float:
    """
    Calculate grip multiplier from tyre temperature.
    Models the characteristic bell curve of tyre grip vs temperature.

    Cold tyre: low grip (rubber hard, poor conformity)
    Optimal temp: peak grip
    Overheated: degraded grip (rubber too soft, chemical degradation)

    Returns:
        Grip multiplier (0.0 to 1.2, where 1.0 = reference grip)
    """
    peak   = compound.peak_grip_temp_c
    window = compound.grip_temp_window_c
    cold   = compound.cold_friction_coeff / compound.peak_friction_coeff

    delta = temp_c - peak

    if delta < 0:
        # Cold side — roughly linear from cold grip at 20°C to peak at peak_temp
        cold_range = peak - 20.0
        if cold_range <= 0:
            return cold
        t = max(0, temp_c - 20.0) / cold_range
        return cold + (1.0 - cold) * t

    else:
        # Hot side — Gaussian decay
        # At peak + window: ~60% of peak
        # At peak + 2×window: ~14% of peak
        factor = np.exp(-0.5 * (delta / window) ** 2)
        return max(0.3, factor)  # minimum 30% grip even overheated


def heat_generation_rate(vertical_load_n: float, velocity_ms: float,
                          slip_angle_deg: float, slip_ratio: float,
                          mu_x: float, mu_y: float) -> float:
    """
    Calculate heat generation rate in tyre contact patch.
    Q_dot = F_friction × v_slip

    Friction power = force × sliding velocity
    Sliding velocity at contact patch ≈ v × |sin(slip_angle)|

    Returns:
        Heat generation rate (Watts)
    """
    # Lateral heat from cornering
    Fy           = vertical_load_n * abs(mu_y)
    v_slip_lat   = velocity_ms * abs(np.sin(np.radians(slip_angle_deg)))
    Q_lateral    = Fy * v_slip_lat

    # Longitudinal heat from braking/acceleration
    Fx           = vertical_load_n * abs(mu_x)
    v_slip_lon   = velocity_ms * abs(slip_ratio)
    Q_longitudinal = Fx * v_slip_lon

    return Q_lateral + Q_longitudinal


def tyre_thermal_step(state: TyreThermalState, compound: TyreCompound,
                       tyre_geom: TyreGeometry, vertical_load_n: float,
                       velocity_ms: float, slip_angle_deg: float,
                       slip_ratio: float, mu_x: float, mu_y: float,
                       dt: float = 0.1) -> TyreThermalState:
    """
    Advance tyre thermal state by time step dt seconds.

    Heat balance:
      dT/dt = (Q_gen - Q_road - Q_air) / (m × Cp)

    where:
      Q_gen  = heat from slip friction
      Q_road = conduction to road surface
      Q_air  = convection to air

    Args:
        state:          Current thermal state
        compound:       Tyre compound properties
        tyre_geom:      Tyre geometry
        vertical_load_n: Vertical load on tyre
        velocity_ms:    Vehicle velocity
        slip_angle_deg: Current slip angle
        slip_ratio:     Current slip ratio
        mu_x, mu_y:     Current friction coefficients
        dt:             Time step (seconds)

    Returns:
        Updated TyreThermalState
    """
    # Tyre mass estimation (kg) — approximate from dimensions
    rubber_volume_m3 = (np.pi * tyre_geom.overall_radius_m**2 -
                         np.pi * (tyre_geom.rim_diameter_in * 25.4/2000)**2) * \
                        tyre_geom.width_mm / 1000.0 * 0.4   # 40% rubber fill
    tyre_mass_kg = rubber_volume_m3 * compound.density_kg_m3

    # Thermal capacity
    thermal_capacity = tyre_mass_kg * compound.specific_heat_j_kgk

    # Heat generation
    Q_gen = heat_generation_rate(
        vertical_load_n, velocity_ms,
        slip_angle_deg, slip_ratio, mu_x, mu_y
    )

    # Contact patch area
    patch_area = tyre_geom.contact_patch_area_m2(vertical_load_n)

    # Heat conduction to road surface
    # Q_road = k × A × (T_surface - T_road) / thickness
    rubber_thickness = tyre_geom.sidewall_height_mm / 1000.0 * 0.3  # tread depth ~30% of sidewall
    if rubber_thickness > 0:
        Q_road = (compound.thermal_conductivity_w_mk * patch_area *
                   (state.surface_temp_c - state.road_temp_c) / rubber_thickness)
    else:
        Q_road = 0.0

    # Heat convection to air
    # Q_air = h × A_surface × (T_surface - T_ambient)
    # h ≈ 25 W/(m²·K) for a tyre at speed
    h_conv = 25.0 + velocity_ms * 0.5   # convection increases with speed
    A_surface = 2 * np.pi * tyre_geom.overall_radius_m * tyre_geom.width_mm / 1000.0
    Q_air = h_conv * A_surface * (state.surface_temp_c - state.ambient_temp_c)

    # Net heat flux
    Q_net = Q_gen - max(0, Q_road) - max(0, Q_air)

    # Temperature change
    if thermal_capacity > 0:
        dT = (Q_net * dt) / thermal_capacity
    else:
        dT = 0.0

    # Update surface temp
    new_surface = state.surface_temp_c + dT

    # Core temp lags surface — time constant ~30s for a road tyre
    tau_core = 30.0
    new_core = state.core_temp_c + (new_surface - state.core_temp_c) * (dt / tau_core)

    # Physical limits
    new_surface = np.clip(new_surface, state.ambient_temp_c - 5, 400.0)
    new_core    = np.clip(new_core, state.ambient_temp_c - 5, 300.0)

    return TyreThermalState(
        surface_temp_c=round(new_surface, 2),
        core_temp_c=round(new_core, 2),
        ambient_temp_c=state.ambient_temp_c,
        road_temp_c=state.road_temp_c,
    )


def simulate_warmup(compound_name: str, tyre_geom: TyreGeometry,
                     vertical_load_n: float = 3500.0,
                     velocity_ms: float = 30.0,
                     slip_angle_deg: float = 3.0,
                     duration_s: float = 120.0,
                     dt: float = 1.0,
                     ambient_temp_c: float = 20.0) -> dict:
    """
    Simulate tyre warmup from cold.
    Returns temperature and grip vs time.
    """
    compound = TYRE_COMPOUNDS.get(compound_name)
    if not compound:
        return {"error": f"Unknown compound: {compound_name}"}

    coeffs = PacejkaCoefficients.from_compound(compound_name)
    state  = TyreThermalState(
        surface_temp_c=ambient_temp_c,
        core_temp_c=ambient_temp_c,
        ambient_temp_c=ambient_temp_c,
        road_temp_c=ambient_temp_c + 10.0,
    )

    time_vals    = []
    surface_vals = []
    core_vals    = []
    grip_vals    = []

    t = 0.0
    while t <= duration_s:
        temp_factor = grip_from_temperature(state.surface_temp_c, compound)
        mu_y = lateral_force_coefficient(slip_angle_deg, coeffs, vertical_load_n, 0, temp_factor)
        mu_x = longitudinal_force_coefficient(0.05, coeffs, vertical_load_n, temp_factor)

        time_vals.append(round(t, 1))
        surface_vals.append(state.surface_temp_c)
        core_vals.append(state.core_temp_c)
        grip_vals.append(round(temp_factor * compound.peak_friction_coeff, 3))

        state = tyre_thermal_step(
            state, compound, tyre_geom, vertical_load_n,
            velocity_ms, slip_angle_deg, 0.05, mu_x, mu_y, dt
        )
        t += dt

    optimal_time = None
    for i, g in enumerate(grip_vals):
        if g >= compound.peak_friction_coeff * 0.95:
            optimal_time = time_vals[i]
            break

    return {
        "compound":       compound_name,
        "peak_grip":      compound.peak_friction_coeff,
        "optimal_temp_c": compound.peak_grip_temp_c,
        "time_s":         time_vals,
        "surface_temp_c": surface_vals,
        "core_temp_c":    core_vals,
        "grip_n_per_n":   grip_vals,
        "time_to_optimal_s": optimal_time,
        "final_surface_c":   round(surface_vals[-1], 1),
        "final_grip":        round(grip_vals[-1], 3),
    }


# ── Load transfer ─────────────────────────────────────────────────────────────

def lateral_load_transfer(vehicle_mass_kg: float, cog_height_m: float,
                            track_width_m: float,
                            lateral_accel_g: float) -> Tuple[float, float]:
    """
    Calculate lateral load transfer under cornering.
    Returns (inner_wheel_load_n, outer_wheel_load_n)

    ΔFz = m × ay × h / t

    Args:
        vehicle_mass_kg: Total vehicle mass
        cog_height_m:    Centre of gravity height
        track_width_m:   Track width (average front/rear)
        lateral_accel_g: Lateral acceleration in g

    Returns:
        (inner_load_n, outer_load_n) — for one axle
    """
    static_load = vehicle_mass_kg * GRAVITY / 2.0   # per side
    transfer = vehicle_mass_kg * lateral_accel_g * GRAVITY * cog_height_m / track_width_m
    inner = max(0.0, static_load - transfer)
    outer = static_load + transfer
    return round(inner, 1), round(outer, 1)


def longitudinal_load_transfer(vehicle_mass_kg: float, cog_height_m: float,
                                 wheelbase_m: float,
                                 longitudinal_accel_g: float) -> Tuple[float, float]:
    """
    Calculate longitudinal load transfer under braking/acceleration.
    Returns (front_axle_load_n, rear_axle_load_n)

    ΔFz = m × ax × h / L

    Braking: load transfers forward (negative ax)
    Acceleration: load transfers rearward (positive ax)
    """
    static_front = vehicle_mass_kg * GRAVITY * 0.5   # 50/50 split approximation
    static_rear  = vehicle_mass_kg * GRAVITY * 0.5
    transfer = vehicle_mass_kg * longitudinal_accel_g * GRAVITY * cog_height_m / wheelbase_m
    front_load = static_front + transfer   # increases under braking
    rear_load  = static_rear  - transfer   # decreases under braking
    return round(max(0, front_load), 1), round(max(0, rear_load), 1)


def max_lateral_acceleration(coeffs: PacejkaCoefficients,
                               vehicle_mass_kg: float, cog_height_m: float,
                               track_width_m: float,
                               aero_downforce_n: float = 0.0,
                               tyre_temp_factor: float = 1.0) -> float:
    """
    Calculate theoretical maximum lateral acceleration (g).
    Iteratively solves: ay = μ_y(Fz) until convergence.

    Higher downforce increases Fz → higher absolute grip force,
    but load sensitivity means μ_y decreases at higher Fz.

    Returns:
        Maximum lateral acceleration in g
    """
    static_load_per_tyre = (vehicle_mass_kg * GRAVITY + aero_downforce_n) / 4.0

    # Iterate to find peak ay
    ay = 1.0   # initial guess
    for _ in range(20):
        # Load transfer at this ay
        inner, outer = lateral_load_transfer(
            vehicle_mass_kg, cog_height_m, track_width_m, ay
        )
        # Use outer tyre load (limiting tyre)
        outer_with_df = outer + aero_downforce_n / 4.0

        # Grip coefficient at this load
        mu = lateral_force_coefficient(
            8.0, coeffs, outer_with_df, 0.0, tyre_temp_factor
        )

        # Required ay vs available ay
        available_ay = mu * (outer_with_df / (vehicle_mass_kg * GRAVITY / 4.0))
        ay = 0.5 * (ay + available_ay)   # damped iteration

    return round(ay, 3)


def max_braking_deceleration(coeffs: PacejkaCoefficients,
                               vehicle_mass_kg: float, cog_height_m: float,
                               wheelbase_m: float,
                               aero_downforce_n: float = 0.0,
                               tyre_temp_factor: float = 1.0) -> float:
    """
    Calculate theoretical maximum braking deceleration (g).
    Accounts for load transfer during braking (loads front tyres more).

    Returns:
        Maximum braking deceleration in g (positive = deceleration)
    """
    ax = 1.0   # initial guess (g)
    for _ in range(20):
        front_load, rear_load = longitudinal_load_transfer(
            vehicle_mass_kg, cog_height_m, wheelbase_m, -ax
        )
        front_load += aero_downforce_n * 0.4
        rear_load  += aero_downforce_n * 0.6

        mu_front = longitudinal_force_coefficient(-0.15, coeffs, front_load, tyre_temp_factor)
        mu_rear  = longitudinal_force_coefficient(-0.15, coeffs, rear_load, tyre_temp_factor)

        F_front = abs(mu_front) * front_load * 2   # two front tyres
        F_rear  = abs(mu_rear) * rear_load * 2     # two rear tyres
        total_braking = F_front + F_rear

        available_ax = total_braking / (vehicle_mass_kg * GRAVITY)
        ax = 0.5 * (ax + available_ax)

    return round(ax, 3)


# ── Slip angle analysis ───────────────────────────────────────────────────────

def slip_angle_sweep(coeffs: PacejkaCoefficients,
                      vertical_load_n: float,
                      compound: TyreCompound,
                      temp_c: float = None,
                      max_angle_deg: float = 20.0,
                      n_points: int = 41) -> dict:
    """
    Sweep through slip angles and compute lateral force.
    Finds peak grip angle and cornering stiffness.

    Returns:
        dict with angles, mu_y values, peak angle, cornering stiffness
    """
    if temp_c is None:
        temp_c = compound.peak_grip_temp_c
    temp_factor = grip_from_temperature(temp_c, compound)

    angles = np.linspace(-max_angle_deg, max_angle_deg, n_points)
    mu_vals = [
        lateral_force_coefficient(a, coeffs, vertical_load_n, 0.0, temp_factor)
        for a in angles
    ]

    # Peak grip angle
    pos_mu  = [m for m in mu_vals if m >= 0]
    peak_mu = max(pos_mu) if pos_mu else 0
    peak_idx = mu_vals.index(peak_mu) if peak_mu in mu_vals else len(mu_vals)//2
    peak_angle = float(angles[peak_idx])

    # Cornering stiffness C_alpha = dFy/d_alpha at alpha=0
    # Approximate from finite difference around zero
    da     = 0.1  # degrees
    mu_plus  = lateral_force_coefficient(da, coeffs, vertical_load_n, 0.0, temp_factor)
    mu_minus = lateral_force_coefficient(-da, coeffs, vertical_load_n, 0.0, temp_factor)
    cornering_stiffness_per_deg = (mu_plus - mu_minus) / (2 * da)

    return {
        "slip_angles_deg":           angles.tolist(),
        "lateral_friction_coeff":    [round(m, 4) for m in mu_vals],
        "peak_friction_coeff":       round(peak_mu, 4),
        "peak_slip_angle_deg":       round(peak_angle, 1),
        "cornering_stiffness_per_deg":round(cornering_stiffness_per_deg, 4),
        "tyre_temp_c":               temp_c,
        "temp_factor":               round(temp_factor, 3),
    }


# ── Full tyre analysis ────────────────────────────────────────────────────────

def analyse_tyre(compound_name: str, tyre_size: str,
                  vehicle_mass_kg: float = 1500.0,
                  cog_height_m: float = 0.45,
                  track_width_m: float = 1.52,
                  wheelbase_m: float = 2.55,
                  aero_downforce_n: float = 0.0,
                  tyre_temp_c: float = None) -> dict:
    """
    Complete tyre performance analysis for a given vehicle setup.

    Args:
        compound_name:   Tyre compound key from TYRE_COMPOUNDS
        tyre_size:       Size string e.g. "265/35R19"
        vehicle_mass_kg: Total vehicle mass
        cog_height_m:    Centre of gravity height
        track_width_m:   Average track width
        wheelbase_m:     Wheelbase
        aero_downforce_n:Total downforce (N)
        tyre_temp_c:     Operating temperature (None = use peak temp)

    Returns:
        Complete performance analysis dict
    """
    compound = TYRE_COMPOUNDS.get(compound_name)
    if not compound:
        return {"error": f"Unknown compound: {compound_name}"}

    # Parse tyre size
    try:
        parts = tyre_size.replace("R", "/").split("/")
        tyre_geom = TyreGeometry(
            width_mm=float(parts[0]),
            aspect_ratio_pct=float(parts[1]),
            rim_diameter_in=float(parts[2]),
        )
    except Exception:
        tyre_geom = TyreGeometry(265, 35, 19)   # default

    coeffs = PacejkaCoefficients.from_compound(compound_name)
    if tyre_temp_c is None:
        tyre_temp_c = compound.peak_grip_temp_c
    temp_factor = grip_from_temperature(tyre_temp_c, compound)

    # Per-tyre vertical load (static)
    static_load_n = (vehicle_mass_kg * GRAVITY + aero_downforce_n) / 4.0

    # Contact patch
    patch_area = tyre_geom.contact_patch_area_m2(static_load_n)
    patch_length = tyre_geom.contact_patch_length_m(static_load_n)

    # Peak lateral grip (at optimal slip angle)
    peak_lateral_mu = lateral_force_coefficient(
        8.0, coeffs, static_load_n, -2.0, temp_factor
    )

    # Peak longitudinal (braking)
    peak_lon_mu = longitudinal_force_coefficient(-0.15, coeffs, static_load_n, temp_factor)

    # Vehicle performance limits
    max_lat_g  = max_lateral_acceleration(
        coeffs, vehicle_mass_kg, cog_height_m, track_width_m, aero_downforce_n, temp_factor
    )
    max_brake_g = max_braking_deceleration(
        coeffs, vehicle_mass_kg, cog_height_m, wheelbase_m, aero_downforce_n, temp_factor
    )

    # Grip circle
    circle = grip_circle(coeffs, static_load_n, temp_factor=temp_factor)

    # Slip angle sweep
    sweep = slip_angle_sweep(coeffs, static_load_n, compound, tyre_temp_c)

    # Warmup estimate
    warmup = simulate_warmup(
        compound_name, tyre_geom, static_load_n, 30.0, 3.0, 120.0, 1.0
    )

    return {
        "compound":         compound_name,
        "tyre_size":        tyre_geom.summary(),
        "operating_temp_c": tyre_temp_c,
        "peak_grip_temp_c": compound.peak_grip_temp_c,
        "temp_factor":      round(temp_factor, 3),

        "contact_patch": {
            "area_m2":      round(patch_area, 5),
            "area_cm2":     round(patch_area * 10000, 1),
            "length_mm":    round(patch_length * 1000, 1),
            "width_mm":     round(tyre_geom.contact_width_m * 1000, 1),
        },

        "grip": {
            "peak_lateral_mu":      round(peak_lateral_mu, 3),
            "peak_longitudinal_mu": round(abs(peak_lon_mu), 3),
            "peak_combined_mu":     circle["peak_combined"],
        },

        "vehicle_limits": {
            "max_lateral_accel_g":  max_lat_g,
            "max_braking_g":        max_brake_g,
            "lateral_force_n":      round(max_lat_g * vehicle_mass_kg * GRAVITY, 0),
            "braking_force_n":      round(max_brake_g * vehicle_mass_kg * GRAVITY, 0),
        },

        "slip_angle_analysis": {
            "peak_slip_angle_deg":  sweep["peak_slip_angle_deg"],
            "cornering_stiffness":  sweep["cornering_stiffness_per_deg"],
        },

        "warmup": {
            "time_to_optimal_s":    warmup.get("time_to_optimal_s") or ">120s",
            "cold_grip_fraction":   round(compound.cold_friction_coeff / compound.peak_friction_coeff, 2),
        },
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Tyre Model Test")
    print("=" * 60)

    # Toyota Supra MK4 — semi slick setup
    result = analyse_tyre(
        compound_name="semi_slick",
        tyre_size="265/35R19",
        vehicle_mass_kg=1520,
        cog_height_m=0.45,
        track_width_m=1.52,
        wheelbase_m=2.55,
        aero_downforce_n=400.0,   # with aero kit
    )

    print("\nToyota Supra MK4 — Semi-Slick 265/35R19 — With Aero Kit")
    print(f"  Tyre size:          {result['tyre_size']['size']}")
    print(f"  Contact patch:      {result['contact_patch']['area_cm2']}cm² "
          f"({result['contact_patch']['length_mm']}mm × {result['contact_patch']['width_mm']}mm)")
    print(f"  Peak temp:          {result['peak_grip_temp_c']}°C (operating: {result['operating_temp_c']}°C)")
    print(f"  Peak lateral μ:     {result['grip']['peak_lateral_mu']}")
    print(f"  Peak longitudinal μ:{result['grip']['peak_longitudinal_mu']}")
    print(f"  Peak combined μ:    {result['grip']['peak_combined_mu']}")
    print(f"  Max lateral accel:  {result['vehicle_limits']['max_lateral_accel_g']}g")
    print(f"  Max braking:        {result['vehicle_limits']['max_braking_g']}g")
    print(f"  Peak slip angle:    {result['slip_angle_analysis']['peak_slip_angle_deg']}°")
    wt = result['warmup']['time_to_optimal_s']
    print(f"  Warmup time:        {wt if wt else '>120s'} to optimal temp")
    print(f"  Cold grip:          {result['warmup']['cold_grip_fraction']*100:.0f}% of peak")

    print("\nCompound comparison at 200kg downforce:")
    for comp in ["slick_soft", "semi_slick", "performance_street", "standard_street"]:
        r = analyse_tyre(comp, "265/35R19", 1520, 0.45, 1.52, 2.55, 200.0)
        warmup = r['warmup']['time_to_optimal_s']
        warmup_str = f"{float(warmup):.0f}s" if warmup is not None and warmup != '>120s' else ">120s"
        print(f"  {comp:25} max_lat={r['vehicle_limits']['max_lateral_accel_g']}g  "
              f"warmup={warmup_str}")

    print("\nEffect of downforce on lateral grip:")
    comp = "semi_slick"
    for df in [0, 200, 500, 1000, 2000]:
        r = analyse_tyre(comp, "265/35R19", 1520, 0.45, 1.52, 2.55, float(df))
        print(f"  DF={df:5}N  max_lat={r['vehicle_limits']['max_lateral_accel_g']}g  "
              f"patch={r['contact_patch']['area_cm2']}cm²")
