"""
physics_engine/vehicle_dynamics.py - Vehicle Dynamics Model

Ties together aerodynamics, tyre_model, thermodynamics, and structural
into a complete vehicle simulation.

Covers:
  1. Vehicle state - mass, geometry, CoG, inertia
  2. Weight transfer - static and dynamic (cornering, braking, acceleration)
  3. Suspension kinematics - camber, toe, roll stiffness distribution
  4. Understeer/oversteer gradient
  5. Simplified lap time simulation (point mass model)
  6. Performance envelope - g-g diagram
  7. Setup sensitivity analysis

Coordinate system: ISO 8855
  X = forward, Y = left, Z = up
  Origin = front axle centre at ground level

References:
  - Milliken & Milliken "Race Car Vehicle Dynamics"
  - Gillespie "Fundamentals of Vehicle Dynamics"
  - Dixon "Tires, Suspension and Handling"
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from aerodynamics import VehicleGeometry, aerodynamic_forces, estimate_vehicle_cd
from tyre_model import (
    TyreGeometry, TyreCompound, PacejkaCoefficients,
    TYRE_COMPOUNDS, lateral_force_coefficient,
    longitudinal_force_coefficient, combined_slip,
    lateral_load_transfer, longitudinal_load_transfer,
    max_lateral_acceleration, max_braking_deceleration,
    grip_from_temperature,
)
from thermodynamics import (
    BrakeDisc, BrakePad, CoolingSystem,
    engine_heat_output, radiator_heat_rejection,
    simulate_brake_event,
)

GRAVITY = 9.81


# ── Named circuits ────────────────────────────────────────────────────────────

CIRCUITS = {
    "suzuka": {
        "name":       "Suzuka Circuit",
        "country":    "Japan",
        "length_m":   5807,
        "straight_m": 640,
        "corners": [
            {"name": "T1 First Corner",  "radius_m": 20,  "length_m": 55},
            {"name": "T2 Dunlop",        "radius_m": 35,  "length_m": 90},
            {"name": "T3 Degner 1",      "radius_m": 28,  "length_m": 70},
            {"name": "T4 Degner 2",      "radius_m": 22,  "length_m": 60},
            {"name": "T5 Hairpin",       "radius_m": 15,  "length_m": 45},
            {"name": "T6 Spoon S1",      "radius_m": 55,  "length_m": 130},
            {"name": "T7 Spoon S2",      "radius_m": 45,  "length_m": 110},
            {"name": "T8 130R",          "radius_m": 130, "length_m": 300},
            {"name": "T9 Casio Chicane", "radius_m": 18,  "length_m": 50},
        ],
    },
    "tsukuba": {
        "name":       "Tsukuba Circuit",
        "country":    "Japan",
        "length_m":   2045,
        "straight_m": 280,
        "corners": [
            {"name": "T1", "radius_m": 30, "length_m": 80},
            {"name": "T2", "radius_m": 20, "length_m": 55},
            {"name": "T3", "radius_m": 45, "length_m": 110},
            {"name": "T4", "radius_m": 25, "length_m": 65},
            {"name": "T5", "radius_m": 35, "length_m": 90},
        ],
    },
    "nurburgring_gp": {
        "name":       "Nurburgring GP Circuit",
        "country":    "Germany",
        "length_m":   5148,
        "straight_m": 700,
        "corners": [
            {"name": "T1 Einfahrt",       "radius_m": 25, "length_m": 65},
            {"name": "T2 Einfahrt 2",     "radius_m": 40, "length_m": 100},
            {"name": "T3 Ford",           "radius_m": 18, "length_m": 50},
            {"name": "T4 Dunlop",         "radius_m": 30, "length_m": 80},
            {"name": "T5 NGK",            "radius_m": 50, "length_m": 120},
            {"name": "T6 Veedol",         "radius_m": 35, "length_m": 90},
            {"name": "T7 Schumacher S",   "radius_m": 22, "length_m": 60},
            {"name": "T8 Mercedes Arena", "radius_m": 60, "length_m": 140},
        ],
    },
    "brands_hatch": {
        "name":       "Brands Hatch GP",
        "country":    "UK",
        "length_m":   4206,
        "straight_m": 500,
        "corners": [
            {"name": "Paddock Hill", "radius_m": 20, "length_m": 55},
            {"name": "Druids",      "radius_m": 18, "length_m": 50},
            {"name": "Graham Hill", "radius_m": 35, "length_m": 90},
            {"name": "Surtees",     "radius_m": 45, "length_m": 110},
            {"name": "McLaren",     "radius_m": 55, "length_m": 130},
            {"name": "Clearways",   "radius_m": 70, "length_m": 160},
        ],
    },
    "laguna_seca": {
        "name":       "WeatherTech Raceway Laguna Seca",
        "country":    "USA",
        "length_m":   3602,
        "straight_m": 450,
        "corners": [
            {"name": "T1",           "radius_m": 25, "length_m": 65},
            {"name": "T2",           "radius_m": 40, "length_m": 100},
            {"name": "T3",           "radius_m": 30, "length_m": 80},
            {"name": "T4",           "radius_m": 20, "length_m": 55},
            {"name": "Corkscrew T8", "radius_m": 15, "length_m": 45},
            {"name": "T9",           "radius_m": 35, "length_m": 90},
            {"name": "T10",          "radius_m": 50, "length_m": 120},
            {"name": "T11 Rainey",   "radius_m": 22, "length_m": 60},
        ],
    },
    "willow_springs": {
        "name":       "Willow Springs International Raceway",
        "country":    "USA",
        "length_m":   4023,
        "straight_m": 800,
        "corners": [
            {"name": "T1 fast right",  "radius_m": 120, "length_m": 280},
            {"name": "T2 horseshoe",   "radius_m": 25,  "length_m": 65},
            {"name": "T3",             "radius_m": 55,  "length_m": 130},
            {"name": "T4 fast sweep",  "radius_m": 90,  "length_m": 210},
            {"name": "T5 hairpin",     "radius_m": 18,  "length_m": 50},
            {"name": "T6 esses",       "radius_m": 35,  "length_m": 90},
        ],
    },
    "bathurst": {
        "name":       "Mount Panorama Circuit",
        "country":    "Australia",
        "length_m":   6213,
        "straight_m": 600,
        "corners": [
            {"name": "T1 Hell Corner",      "radius_m": 18,  "length_m": 50},
            {"name": "T2 Mountain",         "radius_m": 30,  "length_m": 80},
            {"name": "T3 Griffins Bend",    "radius_m": 25,  "length_m": 65},
            {"name": "T4 Sulman Park",      "radius_m": 40,  "length_m": 100},
            {"name": "T5 Skyline",          "radius_m": 35,  "length_m": 90},
            {"name": "T6 The Dipper",       "radius_m": 15,  "length_m": 45},
            {"name": "T7 Forrest Elbow",    "radius_m": 20,  "length_m": 55},
            {"name": "T8 Murray's Corner",  "radius_m": 45,  "length_m": 110},
            {"name": "T9 The Chase",        "radius_m": 22,  "length_m": 60},
        ],
    },
    "spa": {
        "name":       "Circuit de Spa-Francorchamps",
        "country":    "Belgium",
        "length_m":   7004,
        "straight_m": 750,
        "corners": [
            {"name": "La Source",    "radius_m": 15,  "length_m": 45},
            {"name": "Eau Rouge",    "radius_m": 50,  "length_m": 120},
            {"name": "Raidillon",    "radius_m": 80,  "length_m": 190},
            {"name": "Kemmel S1",    "radius_m": 35,  "length_m": 90},
            {"name": "Les Combes",   "radius_m": 18,  "length_m": 50},
            {"name": "Pouhon",       "radius_m": 120, "length_m": 280},
            {"name": "Campus",       "radius_m": 30,  "length_m": 80},
            {"name": "Stavelot",     "radius_m": 45,  "length_m": 110},
            {"name": "Blanchimont",  "radius_m": 150, "length_m": 340},
            {"name": "Bus Stop",     "radius_m": 20,  "length_m": 55},
        ],
    },
}


def get_circuit(circuit_name: str) -> Optional[dict]:
    return CIRCUITS.get(circuit_name.lower().replace(" ", "_"))


# ── Vehicle specification ─────────────────────────────────────────────────────

@dataclass
class VehicleSpec:
    """
    Complete vehicle specification for dynamics simulation.
    All dimensions in metres, mass in kg, angles in degrees.
    """
    name:               str   = "Vehicle"
    drivetrain:         str   = "rwd"

    mass_kg:            float = 1500.0
    fuel_mass_kg:       float = 50.0
    driver_mass_kg:     float = 75.0
    ballast_kg:         float = 0.0

    wheelbase_m:        float = 2.55
    track_front_m:      float = 1.52
    track_rear_m:       float = 1.51
    cog_height_m:       float = 0.45
    cog_x_from_front_m: float = None
    weight_dist_front:  float = 0.52

    roll_stiffness_front_nm_deg: float = 1200.0
    roll_stiffness_rear_nm_deg:  float = 1000.0
    camber_front_deg:   float = -1.5
    camber_rear_deg:    float = -1.5
    toe_front_deg:      float = 0.0
    toe_rear_deg:       float = 0.1
    ride_height_front_m: float = 0.12
    ride_height_rear_m:  float = 0.12

    tyre_compound:      str   = "performance_street"
    tyre_size_front:    str   = "235/40R18"
    tyre_size_rear:     str   = "265/35R19"
    tyre_pressure_kpa:  float = 220.0

    engine_power_hp:    float = 300.0
    engine_torque_nm:   float = 400.0
    final_drive_ratio:  float = 3.9
    tyre_radius_m:      float = 0.32

    brake_bias_front:   float = 0.65
    brake_fluid:        str   = "DOT4"

    aero_geometry:      Optional[VehicleGeometry] = None

    def __post_init__(self):
        if self.cog_x_from_front_m is None:
            self.cog_x_from_front_m = self.wheelbase_m * (1 - self.weight_dist_front)

    @property
    def total_mass_kg(self) -> float:
        return self.mass_kg + self.fuel_mass_kg + self.driver_mass_kg + self.ballast_kg

    @property
    def static_front_load_n(self) -> float:
        return self.total_mass_kg * GRAVITY * self.weight_dist_front

    @property
    def static_rear_load_n(self) -> float:
        return self.total_mass_kg * GRAVITY * (1 - self.weight_dist_front)

    @property
    def static_per_tyre_front_n(self) -> float:
        return self.static_front_load_n / 2.0

    @property
    def static_per_tyre_rear_n(self) -> float:
        return self.static_rear_load_n / 2.0

    @property
    def roll_stiffness_total_nm_deg(self) -> float:
        return self.roll_stiffness_front_nm_deg + self.roll_stiffness_rear_nm_deg

    @property
    def roll_stiffness_front_fraction(self) -> float:
        if self.roll_stiffness_total_nm_deg == 0:
            return 0.5
        return self.roll_stiffness_front_nm_deg / self.roll_stiffness_total_nm_deg

    @property
    def track_avg_m(self) -> float:
        return (self.track_front_m + self.track_rear_m) / 2.0


# ── Weight transfer ───────────────────────────────────────────────────────────

def weight_transfer_cornering(spec: VehicleSpec, lateral_accel_g: float,
                               aero_downforce_n: float = 0.0) -> dict:
    m  = spec.total_mass_kg
    h  = spec.cog_height_m
    ay = lateral_accel_g * GRAVITY

    total_transfer_n = m * ay * h / spec.track_avg_m
    front_transfer   = total_transfer_n * spec.roll_stiffness_front_fraction
    rear_transfer    = total_transfer_n * (1 - spec.roll_stiffness_front_fraction)

    df_front = aero_downforce_n * 0.40
    df_rear  = aero_downforce_n * 0.60

    fl = spec.static_per_tyre_front_n - front_transfer + df_front / 2
    fr = spec.static_per_tyre_front_n + front_transfer + df_front / 2
    rl = spec.static_per_tyre_rear_n  - rear_transfer  + df_rear  / 2
    rr = spec.static_per_tyre_rear_n  + rear_transfer  + df_rear  / 2

    return {
        "lateral_accel_g":  lateral_accel_g,
        "total_transfer_n": round(total_transfer_n, 1),
        "front_transfer_n": round(front_transfer, 1),
        "rear_transfer_n":  round(rear_transfer, 1),
        "loads_n": {
            "front_left":  round(max(0, fl), 1),
            "front_right": round(max(0, fr), 1),
            "rear_left":   round(max(0, rl), 1),
            "rear_right":  round(max(0, rr), 1),
        },
        "inner_front_n":    round(max(0, fl), 1),
        "outer_front_n":    round(max(0, fr), 1),
        "inner_rear_n":     round(max(0, rl), 1),
        "outer_rear_n":     round(max(0, rr), 1),
        "front_load_total": round(max(0, fl) + max(0, fr), 1),
        "rear_load_total":  round(max(0, rl) + max(0, rr), 1),
    }


def weight_transfer_braking(spec: VehicleSpec, longitudinal_accel_g: float,
                             aero_downforce_n: float = 0.0) -> dict:
    m          = spec.total_mass_kg
    h          = spec.cog_height_m
    L          = spec.wheelbase_m
    ax         = longitudinal_accel_g * GRAVITY
    transfer_n = m * ax * h / L

    df_front   = aero_downforce_n * 0.40
    df_rear    = aero_downforce_n * 0.60
    front_load = spec.static_front_load_n + transfer_n + df_front
    rear_load  = spec.static_rear_load_n  - transfer_n + df_rear

    return {
        "longitudinal_accel_g": longitudinal_accel_g,
        "transfer_n":           round(transfer_n, 1),
        "front_axle_load_n":    round(max(0, front_load), 1),
        "rear_axle_load_n":     round(max(0, rear_load), 1),
        "front_per_tyre_n":     round(max(0, front_load) / 2, 1),
        "rear_per_tyre_n":      round(max(0, rear_load) / 2, 1),
        "front_load_pct":       round(max(0, front_load) / (m * GRAVITY) * 100, 1),
        "rear_load_pct":        round(max(0, rear_load)  / (m * GRAVITY) * 100, 1),
    }


# ── Suspension kinematics ─────────────────────────────────────────────────────

def camber_change_in_roll(roll_angle_deg: float) -> float:
    return -roll_angle_deg * 0.7


def roll_angle(spec: VehicleSpec, lateral_accel_g: float) -> float:
    m     = spec.total_mass_kg
    h     = spec.cog_height_m
    ay    = lateral_accel_g * GRAVITY
    K     = spec.roll_stiffness_total_nm_deg
    if K == 0:
        return 0.0
    M_roll = m * ay * h
    K_rad  = K * (180 / np.pi)
    return round(np.degrees(M_roll / K_rad), 2)


def effective_camber(spec: VehicleSpec, lateral_accel_g: float,
                      axle: str = "front") -> dict:
    phi        = roll_angle(spec, lateral_accel_g)
    delta_cam  = camber_change_in_roll(phi)
    static     = spec.camber_front_deg if axle == "front" else spec.camber_rear_deg
    outer_cam  = static + delta_cam
    inner_cam  = static - delta_cam
    return {
        "roll_angle_deg":    phi,
        "static_camber_deg": static,
        "camber_change_deg": round(delta_cam, 2),
        "outer_tyre_deg":    round(outer_cam, 2),
        "inner_tyre_deg":    round(inner_cam, 2),
        "camber_ok":         outer_cam < 0,
    }


# ── Understeer/oversteer ──────────────────────────────────────────────────────

def understeer_gradient(spec: VehicleSpec, compound_name: str,
                          velocity_ms: float = 20.0,
                          aero_downforce_n: float = 0.0) -> dict:
    coeffs   = PacejkaCoefficients.from_compound(compound_name)
    df_front = aero_downforce_n * 0.40
    df_rear  = aero_downforce_n * 0.60

    # Use 1g lateral load transfer to assess steady-state cornering loads
    # This makes roll stiffness distribution affect the result
    wt = weight_transfer_cornering(spec, 1.0, aero_downforce_n)
    # Outer tyre loads at 1g (limiting condition)
    Wf_outer = wt["outer_front_n"]
    Wr_outer = wt["outer_rear_n"]
    # Effective axle load for cornering stiffness calculation
    Wf = wt["front_load_total"]
    Wr = wt["rear_load_total"]
    da = 0.1

    mu_f_p = lateral_force_coefficient(da,  coeffs, Wf_outer, spec.camber_front_deg)
    mu_f_m = lateral_force_coefficient(-da, coeffs, Wf_outer, spec.camber_front_deg)
    mu_r_p = lateral_force_coefficient(da,  coeffs, Wr_outer, spec.camber_rear_deg)
    mu_r_m = lateral_force_coefficient(-da, coeffs, Wr_outer, spec.camber_rear_deg)

    C_alpha_f = ((mu_f_p - mu_f_m) / (2 * da)) * (Wf / 2) * 2
    C_alpha_r = ((mu_r_p - mu_r_m) / (2 * da)) * (Wr / 2) * 2

    if C_alpha_f > 0 and C_alpha_r > 0:
        K_us = (Wf / C_alpha_f - Wr / C_alpha_r) * GRAVITY
    else:
        K_us = 0.0

    v_char_kph = None
    v_crit_kph = None
    if K_us > 0:
        v_char = np.sqrt(spec.wheelbase_m * GRAVITY / K_us) * (180 / np.pi)
        v_char_kph = round(v_char * 3.6, 1)
    if K_us < 0:
        v_crit = np.sqrt(-spec.wheelbase_m * GRAVITY / K_us) * (180 / np.pi)
        v_crit_kph = round(v_crit * 3.6, 1)

    if K_us > 2:
        balance = "significant understeer"
    elif K_us > 0.5:
        balance = "mild understeer"
    elif K_us > -0.5:
        balance = "neutral"
    elif K_us > -2:
        balance = "mild oversteer"
    else:
        balance = "significant oversteer"

    return {
        "understeer_gradient_deg_g":       round(K_us, 3),
        "balance":                         balance,
        "front_cornering_stiffness_n_deg": round(C_alpha_f, 1),
        "rear_cornering_stiffness_n_deg":  round(C_alpha_r, 1),
        "front_axle_load_n":               round(Wf, 1),
        "rear_axle_load_n":                round(Wr, 1),
        "characteristic_speed_kph":        v_char_kph,
        "critical_speed_kph":              v_crit_kph,
        "recommendation":                  _balance_recommendation(K_us, spec),
    }


def _balance_recommendation(K_us, spec):
    if K_us > 2:
        return ("Significant understeer. Increase rear roll stiffness, "
                "reduce front spring rate, or add rear downforce.")
    elif K_us > 0.5:
        return ("Mild understeer. Reduce front toe-in or stiffen rear sway bar.")
    elif K_us > -0.5:
        return "Neutral handling balance. Good setup."
    elif K_us > -2:
        return ("Mild oversteer. Reduce rear roll stiffness or increase front downforce.")
    else:
        return ("WARNING: Significant oversteer. Soften rear bar, add front splitter, "
                "check rear tyre pressures.")


# ── g-g diagram ───────────────────────────────────────────────────────────────

def gg_diagram(spec: VehicleSpec, compound_name: str,
                velocity_ms: float, aero_downforce_n: float = 0.0,
                tyre_temp_factor: float = 1.0,
                n_points: int = 36) -> dict:
    coeffs   = PacejkaCoefficients.from_compound(compound_name)
    max_lat  = max_lateral_acceleration(
        coeffs, spec.total_mass_kg, spec.cog_height_m,
        spec.track_avg_m, aero_downforce_n, tyre_temp_factor
    )
    max_brake = max_braking_deceleration(
        coeffs, spec.total_mass_kg, spec.cog_height_m,
        spec.wheelbase_m, aero_downforce_n, tyre_temp_factor
    )

    if spec.drivetrain == "awd":
        traction_fraction = 1.0
    elif spec.drivetrain == "rwd":
        traction_fraction = (1 - spec.weight_dist_front)
    else:
        traction_fraction = spec.weight_dist_front

    max_drive = max_brake * traction_fraction * 0.9

    angles  = np.linspace(0, 2 * np.pi, n_points)
    ax_vals = []
    ay_vals = []

    for theta in angles:
        ax_scale = max_drive if np.sin(theta) >= 0 else max_brake
        ay_scale = max_lat
        ax = ax_scale * np.sin(theta)
        ay = ay_scale * np.cos(theta)
        if ax_scale > 0 and ay_scale > 0:
            mag = np.sqrt((ax/ax_scale)**2 + (ay/ay_scale)**2 + 1e-10)
            if mag > 1.0:
                ax /= mag
                ay /= mag
        ax_vals.append(round(ax, 3))
        ay_vals.append(round(ay, 3))

    return {
        "velocity_kph":       round(velocity_ms * 3.6, 1),
        "max_lateral_g":      max_lat,
        "max_braking_g":      max_brake,
        "max_acceleration_g": round(max_drive, 3),
        "gg_ax":              ax_vals,
        "gg_ay":              ay_vals,
        "aero_downforce_n":   aero_downforce_n,
        "tyre_compound":      compound_name,
    }


# ── Lap time simulation ───────────────────────────────────────────────────────

def simulate_lap(spec: VehicleSpec, compound_name: str,
                  circuit_corners: List[dict],
                  straight_length_m: float = 500.0,
                  circuit_name: str = "Unknown Circuit",
                  ambient_temp_c: float = 20.0) -> dict:
    coeffs = PacejkaCoefficients.from_compound(compound_name)
    mass   = spec.total_mass_kg
    Cd     = estimate_vehicle_cd(spec.aero_geometry) if spec.aero_geometry else 0.32
    A      = spec.aero_geometry.frontal_area_m2 if spec.aero_geometry else 1.9
    rho    = 1.204

    sectors    = []
    total_time = 0.0
    total_dist = 0.0

    for i, corner in enumerate(circuit_corners):
        R   = corner["radius_m"]
        L   = corner.get("length_m", R * np.pi / 2)

        v_entry_est = np.sqrt(GRAVITY * R * 1.2)
        q           = 0.5 * rho * v_entry_est**2
        df_n        = q * A * 0.3

        mu_lat   = max_lateral_acceleration(
            coeffs, mass, spec.cog_height_m, spec.track_avg_m, df_n
        )
        v_corner = np.sqrt(mu_lat * GRAVITY * R)
        F_drag   = 0.5 * rho * Cd * A * v_corner**2
        t_corner = L / max(v_corner, 0.1)

        v_straight  = min(
            np.sqrt(2 * spec.engine_power_hp * 745.7 * straight_length_m / mass),
            spec.engine_power_hp * 745.7 / max(F_drag, 1.0)
        )
        v_straight  = min(v_straight, 80.0)

        ax_brake = max_braking_deceleration(
            coeffs, mass, spec.cog_height_m, spec.wheelbase_m, df_n
        ) * GRAVITY

        if v_straight > v_corner and ax_brake > 0:
            brake_dist = (v_straight**2 - v_corner**2) / (2 * ax_brake)
            t_brake    = (v_straight - v_corner) / ax_brake
        else:
            brake_dist = 0.0
            t_brake    = 0.0

        F_traction = spec.engine_power_hp * 745.7 / max(v_corner + 5, 1.0)
        ax_accel   = min(F_traction / mass, mu_lat * GRAVITY * 0.8)
        if ax_accel > 0:
            accel_dist = (v_straight**2 - v_corner**2) / (2 * ax_accel)
            t_accel    = (v_straight - v_corner) / ax_accel
        else:
            accel_dist = 0.0
            t_accel    = 0.0

        straight_remaining = max(0, straight_length_m - brake_dist - accel_dist)
        t_straight         = straight_remaining / max(v_straight, 0.1)
        sector_time        = t_corner + t_brake + t_accel + t_straight
        sector_dist        = L + brake_dist + accel_dist + straight_remaining

        total_time += sector_time
        total_dist += sector_dist

        sectors.append({
            "corner":         corner.get("name", f"Corner {i+1}"),
            "radius_m":       R,
            "v_corner_kph":   round(v_corner * 3.6, 1),
            "v_straight_kph": round(v_straight * 3.6, 1),
            "t_corner_s":     round(t_corner, 2),
            "t_brake_s":      round(t_brake, 2),
            "t_accel_s":      round(t_accel, 2),
            "t_straight_s":   round(t_straight, 2),
            "sector_time_s":  round(sector_time, 2),
            "lateral_accel_g":round(v_corner**2 / (R * GRAVITY), 3),
        })

    lap_time_min = int(total_time // 60)
    lap_time_sec = total_time % 60

    return {
        "vehicle":          spec.name,
        "circuit":          circuit_name,
        "compound":         compound_name,
        "lap_time_s":       round(total_time, 2),
        "lap_time_str":     f"{lap_time_min}:{lap_time_sec:06.3f}",
        "total_distance_m": round(total_dist),
        "avg_speed_kph":    round(total_dist / total_time * 3.6, 1) if total_time > 0 else 0,
        "sectors":          sectors,
        "n_corners":        len(circuit_corners),
    }


# ── Setup sensitivity ─────────────────────────────────────────────────────────

def setup_sensitivity(spec: VehicleSpec, compound_name: str,
                       velocity_ms: float = 30.0,
                       aero_downforce_n: float = 0.0) -> dict:
    baseline = understeer_gradient(spec, compound_name, velocity_ms, aero_downforce_n)
    results  = {"baseline": baseline, "sensitivities": {}}

    def test_change(field_name, delta):
        d = {f: getattr(spec, f) for f in spec.__dataclass_fields__}
        if field_name in d and isinstance(d[field_name], (int, float)):
            d[field_name] = d[field_name] + delta
        spec_mod = VehicleSpec(**d)
        result   = understeer_gradient(spec_mod, compound_name, velocity_ms, aero_downforce_n)
        d_kus    = result["understeer_gradient_deg_g"] - baseline["understeer_gradient_deg_g"]
        return {
            "delta_applied": delta,
            "new_Kus":       result["understeer_gradient_deg_g"],
            "delta_Kus":     round(d_kus, 4),
            "direction":     "more understeer" if d_kus > 0 else "more oversteer",
            "balance":       result["balance"],
        }

    results["sensitivities"]["front_roll_stiffness_+100Nm_deg"] = test_change("roll_stiffness_front_nm_deg", 100)
    results["sensitivities"]["rear_roll_stiffness_+100Nm_deg"]  = test_change("roll_stiffness_rear_nm_deg",  100)
    results["sensitivities"]["front_camber_-0.5deg"]            = test_change("camber_front_deg", -0.5)
    results["sensitivities"]["rear_camber_-0.5deg"]             = test_change("camber_rear_deg",  -0.5)
    results["sensitivities"]["weight_dist_front_+2pct"]         = test_change("weight_dist_front", 0.02)

    return results


# ── Full vehicle analysis ─────────────────────────────────────────────────────

def full_vehicle_analysis(spec: VehicleSpec, compound_name: str,
                           velocity_kph: float = 100.0,
                           lateral_accel_g: float = 1.0,
                           braking_g: float = 1.0,
                           ambient_temp_c: float = 20.0) -> dict:
    velocity_ms = velocity_kph / 3.6
    aero_df_n   = 0.0
    aero_result = None

    if spec.aero_geometry:
        aero_result = aerodynamic_forces(spec.aero_geometry, velocity_ms, ambient_temp_c)
        aero_df_n   = max(0, aero_result["downforce_n"])

    wt_corner   = weight_transfer_cornering(spec, lateral_accel_g, aero_df_n)
    wt_brake    = weight_transfer_braking(spec, braking_g, aero_df_n)
    camber_f    = effective_camber(spec, lateral_accel_g, "front")
    camber_r    = effective_camber(spec, lateral_accel_g, "rear")
    roll_deg    = roll_angle(spec, lateral_accel_g)
    balance     = understeer_gradient(spec, compound_name, velocity_ms, aero_df_n)
    gg          = gg_diagram(spec, compound_name, velocity_ms, aero_df_n)
    sensitivity = setup_sensitivity(spec, compound_name, velocity_ms, aero_df_n)

    return {
        "vehicle":        spec.name,
        "velocity_kph":   velocity_kph,
        "ambient_temp_c": ambient_temp_c,
        "aero":           aero_result,
        "weight_transfer": {"cornering": wt_corner, "braking": wt_brake},
        "suspension":     {"roll_angle_deg": roll_deg, "front_camber": camber_f, "rear_camber": camber_r},
        "balance":        balance,
        "gg_diagram":     gg,
        "sensitivity":    sensitivity,
        "performance_limits": {
            "max_lateral_g":  gg["max_lateral_g"],
            "max_braking_g":  gg["max_braking_g"],
            "max_accel_g":    gg["max_acceleration_g"],
        },
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Vehicle Dynamics Test")
    print("=" * 60)

    supra_aero = VehicleGeometry(
        length_m=4.515, width_m=1.810, height_m=1.275,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        ride_height_m=0.100, windscreen_rake_deg=28, body_style="fastback",
        baseline_cd=0.31, baseline_cl=0.18,
        has_rear_wing=True, wing_span_m=1.400, wing_chord_m=0.250,
        wing_aoa_deg=12.0, wing_profile="NACA2412",
        has_front_splitter=True, splitter_length_m=0.080, splitter_width_m=1.600,
        has_underbody_diffuser=True, diffuser_angle_deg=8.0,
    )

    supra = VehicleSpec(
        name="Toyota Supra MK4 500whp",
        drivetrain="rwd",
        mass_kg=1520, fuel_mass_kg=40, driver_mass_kg=75,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        cog_height_m=0.45, weight_dist_front=0.52,
        roll_stiffness_front_nm_deg=1400, roll_stiffness_rear_nm_deg=900,
        camber_front_deg=-2.0, camber_rear_deg=-1.5,
        engine_power_hp=588,
        tyre_compound="semi_slick",
        tyre_size_front="235/40R18", tyre_size_rear="265/35R19",
        brake_bias_front=0.65,
        aero_geometry=supra_aero,
    )

    print("\nFull vehicle analysis at 150kph, 1.5g cornering:")
    result = full_vehicle_analysis(supra, "semi_slick", velocity_kph=150.0,
                                   lateral_accel_g=1.5, braking_g=1.2)

    if result["aero"]:
        print(f"\nAero at 150kph:")
        print(f"  Downforce:        {result['aero']['downforce_kg']}kg")
        print(f"  Drag:             {result['aero']['drag_kg']}kg")
        print(f"  Drag power:       {result['aero']['drag_power_hp']}hp")

    wt = result["weight_transfer"]["cornering"]
    print(f"\nWeight transfer (1.5g cornering):")
    print(f"  Front transfer:   {wt['front_transfer_n']}N")
    print(f"  Rear transfer:    {wt['rear_transfer_n']}N")
    print(f"  Outer front:      {wt['outer_front_n']}N")
    print(f"  Outer rear:       {wt['outer_rear_n']}N")
    print(f"  Inner front:      {wt['inner_front_n']}N")

    susp = result["suspension"]
    print(f"\nSuspension:")
    print(f"  Roll angle:       {susp['roll_angle_deg']}deg")
    print(f"  Outer front cam:  {susp['front_camber']['outer_tyre_deg']}deg")
    print(f"  Outer rear cam:   {susp['rear_camber']['outer_tyre_deg']}deg")

    bal = result["balance"]
    print(f"\nHandling balance:")
    print(f"  Understeer grad:  {bal['understeer_gradient_deg_g']} deg/g")
    print(f"  Balance:          {bal['balance']}")
    print(f"  -> {bal['recommendation']}")

    pl = result["performance_limits"]
    print(f"\nPerformance limits:")
    print(f"  Max lateral:      {pl['max_lateral_g']}g")
    print(f"  Max braking:      {pl['max_braking_g']}g")
    print(f"  Max acceleration: {pl['max_accel_g']}g")

    print(f"\nSetup sensitivity (effect on understeer gradient):")
    for param, sens in result["sensitivity"]["sensitivities"].items():
        print(f"  {param:40} dKus={sens['delta_Kus']:+.4f} ({sens['direction']})")

    # Lap time on named circuits
    for circuit_key in ["suzuka", "tsukuba", "spa"]:
        circuit = CIRCUITS[circuit_key]
        lap = simulate_lap(
            supra, "semi_slick",
            circuit["corners"],
            straight_length_m=circuit["straight_m"],
            circuit_name=circuit["name"],
        )
        print(f"\nLap time — {lap['circuit']} ({circuit['country']}, {circuit['length_m']}m):")
        print(f"  Estimated lap:  {lap['lap_time_str']}")
        print(f"  Avg speed:      {lap['avg_speed_kph']}kph")
        print(f"  Corner breakdown:")
        for s in lap["sectors"]:
            print(f"    {s['corner']:22} v={s['v_corner_kph']:5.1f}kph  "
                  f"lat={s['lateral_accel_g']:.2f}g  t={s['sector_time_s']:.2f}s")
