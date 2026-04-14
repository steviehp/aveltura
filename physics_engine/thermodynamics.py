"""
physics_engine/thermodynamics.py - Thermal Analysis Engine

Covers:
  1. Brake thermal model
  2. Engine bay heat model
  3. Turbocharger thermal model
  4. Intercooler analysis
  5. Integrated full thermal analysis

All temperatures Celsius at interfaces, Kelvin internally.
All energy in Joules, power in Watts.

References:
  - Limpert, R. "Brake Design and Safety"
  - Heywood, J.B. "Internal Combustion Engine Fundamentals"
  - SAE Technical Papers on thermal management
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from materials_db import MATERIALS, get_material

GRAVITY          = 9.81
STEFAN_BOLTZMANN = 5.67e-8


# ── Brake disc ────────────────────────────────────────────────────────────────

@dataclass
class BrakeDisc:
    outer_radius_m:        float
    inner_radius_m:        float
    thickness_m:           float
    n_vanes:               int   = 32
    material_name:         str   = "Cast Iron (Grey, Brake Grade)"
    pad_friction_radius_m: Optional[float] = None

    @property
    def swept_area_m2(self) -> float:
        return np.pi * (self.outer_radius_m**2 - self.inner_radius_m**2)

    @property
    def disc_volume_m3(self) -> float:
        return self.swept_area_m2 * self.thickness_m

    @property
    def disc_mass_kg(self) -> float:
        mat = get_material(self.material_name)
        return self.disc_volume_m3 * (mat.density_kg_m3 if mat else 7150)

    @property
    def thermal_capacity_j_k(self) -> float:
        mat = get_material(self.material_name)
        cp  = mat.specific_heat_j_kgk if mat else 460.0
        return self.disc_mass_kg * cp

    @property
    def effective_radius_m(self) -> float:
        if self.pad_friction_radius_m:
            return self.pad_friction_radius_m
        return (self.outer_radius_m + self.inner_radius_m) / 2.0

    def summary(self) -> dict:
        return {
            "outer_diameter_mm":    round(self.outer_radius_m * 2000, 0),
            "thickness_mm":         round(self.thickness_m * 1000, 0),
            "swept_area_cm2":       round(self.swept_area_m2 * 10000, 1),
            "mass_kg":              round(self.disc_mass_kg, 2),
            "thermal_capacity_j_k": round(self.thermal_capacity_j_k, 1),
            "material":             self.material_name,
            "vented":               self.n_vanes > 0,
        }


@dataclass
class BrakePad:
    friction_coeff: float = 0.40
    area_m2:        float = 0.004
    compound:       str   = "street"
    max_temp_c:     float = 400.0
    fade_temp_c:    float = 350.0


BRAKE_FLUID_BOILING = {
    "DOT3":         {"dry_boiling_c": 205, "wet_boiling_c": 140, "notes": "Minimum spec."},
    "DOT4":         {"dry_boiling_c": 230, "wet_boiling_c": 155, "notes": "Common OEM fluid."},
    "DOT5.1":       {"dry_boiling_c": 270, "wet_boiling_c": 180, "notes": "High performance glycol."},
    "Motul RBF600": {"dry_boiling_c": 312, "wet_boiling_c": 216, "notes": "Racing fluid."},
    "Motul RBF660": {"dry_boiling_c": 325, "wet_boiling_c": 204, "notes": "Extreme performance. Mandatory for sustained track use."},
    "Castrol SRF":  {"dry_boiling_c": 310, "wet_boiling_c": 270, "notes": "Very high wet boiling point."},
}


def braking_heat_input(vehicle_mass_kg: float, velocity_initial_ms: float,
                        velocity_final_ms: float,
                        braking_fraction: float = 0.7) -> float:
    """Q = 0.5 * m * (v_i^2 - v_f^2) * braking_fraction"""
    delta_ke = 0.5 * vehicle_mass_kg * (velocity_initial_ms**2 - velocity_final_ms**2)
    return max(0.0, delta_ke * braking_fraction)


def brake_heat_distribution(brake_bias_front: float = 0.65) -> Tuple[float, float]:
    return brake_bias_front, 1.0 - brake_bias_front


def disc_temperature_rise(heat_j: float, disc: BrakeDisc,
                           n_discs_on_axle: int = 2) -> float:
    """DeltaT = Q / (n * C_thermal)"""
    return (heat_j / n_discs_on_axle) / disc.thermal_capacity_j_k


def disc_cooling_rate(disc: BrakeDisc, disc_temp_c: float,
                       ambient_temp_c: float, velocity_ms: float,
                       n_vane_channels: int = None) -> float:
    """Convection + radiation cooling rate (W)."""
    disc_temp_k    = disc_temp_c + 273.15
    ambient_temp_k = ambient_temp_c + 273.15
    delta_t        = disc_temp_c - ambient_temp_c
    if delta_t <= 0:
        return 0.0

    n_vanes  = n_vane_channels or disc.n_vanes
    h_ext    = 25.0 + velocity_ms * 1.5
    A_ext    = disc.swept_area_m2 * 2
    Q_conv   = h_ext * A_ext * delta_t

    if n_vanes > 0:
        vane_area = (disc.swept_area_m2 / n_vanes) * 0.6
        h_vane    = 45.0 + velocity_ms * 2.0
        Q_conv   += h_vane * (vane_area * n_vanes * 2) * delta_t

    Q_rad = 0.85 * STEFAN_BOLTZMANN * A_ext * (disc_temp_k**4 - ambient_temp_k**4)
    return Q_conv + Q_rad


def simulate_brake_event(vehicle_mass_kg: float,
                          v_initial_kph: float, v_final_kph: float,
                          front_disc: BrakeDisc, rear_disc: BrakeDisc,
                          initial_disc_temp_c: float = 80.0,
                          ambient_temp_c: float = 20.0,
                          brake_bias_front: float = 0.65,
                          brake_fluid: str = "Motul RBF660",
                          brake_pad: BrakePad = None) -> dict:
    if brake_pad is None:
        brake_pad = BrakePad()

    v_i = v_initial_kph / 3.6
    v_f = v_final_kph  / 3.6

    total_heat = braking_heat_input(vehicle_mass_kg, v_i, v_f)
    f_front, f_rear = brake_heat_distribution(brake_bias_front)

    front_heat = total_heat * f_front
    rear_heat  = total_heat * f_rear
    front_rise = disc_temperature_rise(front_heat, front_disc, 2)
    rear_rise  = disc_temperature_rise(rear_heat,  rear_disc,  2)
    front_temp = initial_disc_temp_c + front_rise
    rear_temp  = initial_disc_temp_c + rear_rise

    fluid_data   = BRAKE_FLUID_BOILING.get(brake_fluid, BRAKE_FLUID_BOILING["DOT4"])
    boiling_risk = front_temp > fluid_data["wet_boiling_c"] * 0.85
    pad_fade     = front_temp > brake_pad.fade_temp_c
    fluid_temp   = initial_disc_temp_c + front_rise * 0.6

    return {
        "braking_event": {
            "v_initial_kph":  v_initial_kph,
            "v_final_kph":    v_final_kph,
            "total_heat_kj":  round(total_heat / 1000, 1),
            "front_heat_kj":  round(front_heat / 1000, 1),
            "rear_heat_kj":   round(rear_heat  / 1000, 1),
        },
        "temperatures": {
            "initial_c":      initial_disc_temp_c,
            "front_disc_c":   round(front_temp, 1),
            "rear_disc_c":    round(rear_temp,  1),
            "front_rise_c":   round(front_rise, 1),
            "rear_rise_c":    round(rear_rise,  1),
            "fluid_est_c":    round(fluid_temp, 1),
        },
        "risk_assessment": {
            "brake_fluid":      brake_fluid,
            "fluid_wet_boil_c": fluid_data["wet_boiling_c"],
            "boiling_risk":     boiling_risk,
            "pad_fade_risk":    pad_fade,
            "pad_max_temp_c":   brake_pad.max_temp_c,
            "recommendation":   _brake_recommendation(
                front_temp, fluid_data, brake_pad, boiling_risk, pad_fade
            ),
        },
        "disc_specs": {
            "front": front_disc.summary(),
            "rear":  rear_disc.summary(),
        },
    }


def _brake_recommendation(disc_temp, fluid_data, pad, boiling_risk, pad_fade):
    if boiling_risk and pad_fade:
        return ("CRITICAL: Fluid boiling risk AND pad fade. "
                "Upgrade to Motul RBF660 and switch to Hawk DTC-60 pads.")
    elif boiling_risk:
        return (f"WARNING: Fluid approaching boiling point. "
                f"Upgrade to {fluid_data.get('notes', 'high-temp fluid')}. "
                f"Consider brake ducting.")
    elif pad_fade:
        return "WARNING: Pad fade risk. Switch to Hawk DTC-60 or Ferodo DS2500."
    elif disc_temp > 400:
        return "Temperatures high. Ensure adequate brake cooling."
    else:
        return "Temperatures within acceptable range."


# ── Cooling system ────────────────────────────────────────────────────────────

@dataclass
class CoolingSystem:
    radiator_area_m2:       float = 0.36
    radiator_thickness_m:   float = 0.034
    n_rows:                 int   = 2
    radiator_material:      str   = "aluminium"
    has_oil_cooler:         bool  = False
    oil_cooler_area_m2:     float = 0.0
    oil_cooler_rows:        int   = 0
    has_intercooler:        bool  = False
    intercooler_area_m2:    float = 0.0
    intercooler_efficiency: float = 0.85
    coolant_type:           str   = "50/50 ethylene glycol"
    coolant_flow_lpm:       float = 80.0
    thermostat_temp_c:      float = 85.0
    max_coolant_temp_c:     float = 110.0

    @property
    def coolant_flow_m3_s(self) -> float:
        return self.coolant_flow_lpm / 60000.0

    @property
    def radiator_effectiveness(self) -> float:
        return min(0.95, 0.65 + (self.n_rows - 1) * 0.08)


def engine_heat_output(power_hp: float, thermal_efficiency: float = 0.38) -> dict:
    """
    Empirical engine heat rejection model.
    Fractions of engine power: 30% coolant, 40% exhaust, 8% oil, 5% radiation.
    Based on published dyno and thermal data for turbocharged engines.
    """
    power_w      = power_hp * 745.7
    heat_coolant = power_w * 0.30
    heat_exhaust = power_w * 0.40
    heat_oil     = power_w * 0.08
    heat_rad     = power_w * 0.05
    heat_total   = heat_coolant + heat_exhaust + heat_oil + heat_rad
    return {
        "engine_power_w":     round(power_w),
        "fuel_energy_w":      round(power_w / thermal_efficiency),
        "heat_rejected_w":    round(heat_total),
        "heat_to_coolant_w":  round(heat_coolant),
        "heat_to_exhaust_w":  round(heat_exhaust),
        "heat_to_oil_w":      round(heat_oil),
        "heat_radiation_w":   round(heat_rad),
        "thermal_efficiency": thermal_efficiency,
    }


def radiator_heat_rejection(cooling: CoolingSystem,
                              coolant_temp_c: float,
                              ambient_temp_c: float,
                              vehicle_velocity_ms: float,
                              heat_input_w: float) -> dict:
    """
    NTU-Effectiveness method for radiator heat rejection.
    Q = epsilon * C_min * (T_coolant - T_ambient)
    Steady state: T_coolant_ss = T_ambient + Q_input / (epsilon * C_min)
    """
    # Airflow through radiator — much less than free stream due to restriction
    # Typical radiator face velocity: 2-8 m/s at highway speed
    v_air       = max(0.5, vehicle_velocity_ms * 0.12)   # ~12% of vehicle speed at radiator face
    rho_air     = 1.204
    # Air mass flow through radiator core
    m_dot_air   = rho_air * v_air * cooling.radiator_area_m2
    # Coolant mass flow
    rho_coolant = 1070.0
    cp_coolant  = 3600.0
    m_dot_cool  = cooling.coolant_flow_m3_s * rho_coolant
    # Heat capacity rates (W/K)
    C_air       = m_dot_air  * 1005.0
    C_cool      = m_dot_cool * cp_coolant
    C_min       = min(C_air, C_cool)
    C_max       = max(C_air, C_cool)
    C_r         = C_min / C_max if C_max > 0 else 0

    # Overall heat transfer coefficient — radiator UA value
    # Typical car radiator: UA = 1500-4000 W/K depending on size and airspeed
    UA  = (1500 + v_air * 150) * cooling.n_rows * (cooling.radiator_area_m2 / 0.36)
    NTU = UA / max(C_min, 1.0)

    # Effectiveness — cross flow, both fluids unmixed approximation
    if C_r < 0.999 and C_r > 0:
        epsilon = (1 - np.exp(-NTU * (1 - C_r))) / (1 - C_r * np.exp(-NTU * (1 - C_r)))
    elif C_r >= 0.999:
        epsilon = NTU / (1 + NTU)
    else:
        epsilon = 1 - np.exp(-NTU)

    epsilon  = np.clip(epsilon, 0.0, 0.92)
    Q_max    = C_min * (coolant_temp_c - ambient_temp_c)
    Q_actual = epsilon * Q_max

    # Steady state coolant temp: T_ss = T_ambient + Q_input / (epsilon * C_min)
    eff_C_min  = max(epsilon * C_min, 10.0)
    dt_steady  = heat_input_w / eff_C_min
    coolant_ss = ambient_temp_c + min(dt_steady, 150.0)
    coolant_out = coolant_temp_c - Q_actual / max(C_cool, 1.0)

    return {
        "heat_input_w":           round(heat_input_w),
        "heat_rejected_w":        round(Q_actual),
        "heat_deficit_w":         round(max(0, heat_input_w - Q_actual)),
        "coolant_inlet_c":        coolant_temp_c,
        "coolant_outlet_c":       round(coolant_out, 1),
        "coolant_steady_state_c": round(coolant_ss, 1),
        "overheat_risk":          coolant_ss > cooling.max_coolant_temp_c,
        "airflow_velocity_ms":    round(v_air, 1),
        "air_mass_flow_kg_s":     round(m_dot_air, 3),
        "radiator_effectiveness": round(epsilon, 3),
        "radiator_capacity_w":    round(Q_max),
        "margin_w":               round(Q_actual - heat_input_w),
        "recommendation":         _cooling_recommendation(
            coolant_ss, cooling.max_coolant_temp_c, Q_actual, heat_input_w
        ),
    }


def _cooling_recommendation(ss_temp, max_temp, q_rejected, q_input):
    deficit = q_input - q_rejected
    if ss_temp > max_temp + 10:
        return (f"CRITICAL: Coolant will overheat at {ss_temp:.0f}C. "
                f"Cooling deficit: {deficit/1000:.1f}kW. Upgrade radiator or add oil cooler.")
    elif ss_temp > max_temp:
        return (f"WARNING: Steady state {ss_temp:.0f}C near limit. "
                f"Add oil cooler or upgrade to 3-row radiator.")
    elif deficit > 5000:
        return f"Marginal. Heat deficit {deficit/1000:.1f}kW at this speed."
    else:
        return f"Cooling adequate. Margin: {-deficit/1000:.1f}kW."


# ── Turbocharger thermal model ────────────────────────────────────────────────

def turbine_inlet_temperature(power_hp: float, boost_psi: float,
                                displacement_cc: float,
                                air_fuel_ratio: float = 11.5,
                                compression_ratio: float = 9.0) -> dict:
    """
    Estimate turbine inlet temperature (TIT) from engine parameters.
    Based on empirical EGT data for turbocharged engines.
    Safe limits: cast iron 850C, stainless 900C, Inconel 1050C.
    """
    stoich_afr      = 14.7
    lambda_val      = air_fuel_ratio / stoich_afr
    t_base_c        = 680.0

    if lambda_val < 0.8:
        t_lambda = t_base_c + 120 * (0.8 - lambda_val) / 0.2
    elif lambda_val < 0.95:
        t_lambda = t_base_c + 60 * (0.95 - lambda_val) / 0.15
    else:
        t_lambda = t_base_c - 30 * (lambda_val - 1.0)

    boost_bar       = boost_psi * 0.0689476
    t_boost         = t_lambda + boost_bar * 35.0
    t_cr            = t_boost - (compression_ratio - 9.0) * 15.0
    power_per_litre = power_hp / (displacement_cc / 1000.0)
    tit_c           = round(t_cr + (power_per_litre - 100) * 0.8, 0)

    manifold_limits = {"Cast iron": 850, "Stainless 304": 900, "Inconel": 1050}
    turbine_limits  = {
        "Standard alloy wheel": 950,
        "Titanium wheel":       1050,
        "Inconel wheel":        1100,
    }
    manifold_safe   = {k: tit_c <= v for k, v in manifold_limits.items()}
    turbine_safe    = {k: tit_c <= v for k, v in turbine_limits.items()}
    oiling_risk     = tit_c > 850

    return {
        "turbine_inlet_temp_c":   tit_c,
        "boost_psi":              boost_psi,
        "air_fuel_ratio":         air_fuel_ratio,
        "lambda":                 round(lambda_val, 3),
        "power_per_litre_hp_l":   round(power_per_litre, 1),
        "safe_for_manifold":      manifold_safe,
        "safe_for_turbine":       turbine_safe,
        "oil_coking_risk":        oiling_risk,
        "oil_coking_note":        (
            "Oil coking risk at shutdown — install turbo timer, allow 2min idle cooldown."
            if oiling_risk else "Oil coking risk low."
        ),
        "recommendations": _tit_recommendations(tit_c, manifold_safe, turbine_safe),
    }


def _tit_recommendations(tit_c, manifold_safe, turbine_safe):
    recs = []
    if tit_c > 1000:
        recs.append("CRITICAL: TIT extremely high. Richen mixture, reduce boost, upgrade to water-cooled turbo.")
    elif tit_c > 900:
        recs.append("WARNING: TIT elevated. Use Inconel manifold. Water-cooled bearing housing recommended.")
    if not manifold_safe.get("Stainless 304"):
        recs.append("Stainless manifold insufficient. Upgrade to Inconel.")
    if not manifold_safe.get("Cast iron"):
        recs.append("Cast iron manifold UNSAFE at this TIT. Replace immediately.")
    if tit_c > 750:
        recs.append("Install heat wrap on exhaust manifold and turbo inlet.")
    if tit_c > 850:
        recs.append("Install turbo timer — minimum 2min idle cooldown before shutdown.")
        recs.append("Upgrade to high-stability oil (Motul 300V or similar).")
    return recs if recs else ["TIT within safe limits for standard turbo hardware."]


# ── Intercooler model ─────────────────────────────────────────────────────────

def intercooler_analysis(boost_psi: float, intake_air_temp_c: float,
                          ambient_temp_c: float,
                          intercooler_efficiency: float = 0.85,
                          engine_power_hp: float = 400.0) -> dict:
    """
    Charge air temperature after turbo compressor and intercooler.
    T_compressor_out = T_ambient + isentropic_rise / eta_isentropic
    T_ic_out = T_compressor_out - efficiency * (T_compressor_out - T_ambient)
    """
    boost_bar      = boost_psi * 0.0689476
    pressure_ratio = (1.013 + boost_bar) / 1.013
    gamma          = 1.4
    t_rise         = intake_air_temp_c * (pressure_ratio**((gamma-1)/gamma) - 1)
    t_comp_out     = ambient_temp_c + t_rise / 0.72
    t_ic_out       = t_comp_out - intercooler_efficiency * (t_comp_out - ambient_temp_c)
    density_ratio  = (t_comp_out + 273.15) / (t_ic_out + 273.15)
    power_gain_pct = (density_ratio - 1.0) * 100.0
    knock_risk     = t_ic_out > 60.0
    heat_soak_temp = t_ic_out + (engine_power_hp / 100.0) * 5.0

    return {
        "boost_psi":                 boost_psi,
        "pressure_ratio":            round(pressure_ratio, 2),
        "compressor_outlet_temp_c":  round(t_comp_out, 1),
        "intercooler_outlet_temp_c": round(t_ic_out, 1),
        "temperature_drop_c":        round(t_comp_out - t_ic_out, 1),
        "intercooler_efficiency":    intercooler_efficiency,
        "charge_density_gain_pct":   round((density_ratio - 1) * 100, 1),
        "estimated_power_gain_pct":  round(power_gain_pct, 1),
        "knock_risk":                knock_risk,
        "heat_soak_temp_c":          round(heat_soak_temp, 1),
        "recommendations":           _ic_recommendations(t_ic_out, intercooler_efficiency, knock_risk),
    }


def _ic_recommendations(t_out, efficiency, knock_risk):
    recs = []
    if knock_risk:
        recs.append(f"Charge temp {t_out:.0f}C — knock risk. Upgrade intercooler or add water-methanol injection.")
    if efficiency < 0.80:
        recs.append("Intercooler efficiency below 80%. Upgrade core or improve airflow.")
    if t_out > 50:
        recs.append("Consider water-methanol injection for additional charge cooling.")
    return recs if recs else [f"Charge temp {t_out:.0f}C — acceptable."]


# ── Integrated thermal analysis ───────────────────────────────────────────────

def full_thermal_analysis(engine_power_hp: float,
                           boost_psi: float,
                           displacement_cc: float,
                           compression_ratio: float,
                           vehicle_mass_kg: float,
                           cooling: CoolingSystem,
                           front_disc: BrakeDisc,
                           rear_disc: BrakeDisc,
                           v_max_kph: float = 250.0,
                           ambient_temp_c: float = 20.0,
                           brake_fluid: str = "Motul RBF660") -> dict:
    """Full thermal analysis — engine cooling, turbo, intercooler, brakes."""
    eng_heat = engine_heat_output(engine_power_hp)

    cooling_hwy = radiator_heat_rejection(
        cooling,
        coolant_temp_c=cooling.thermostat_temp_c + 10,
        ambient_temp_c=ambient_temp_c,
        vehicle_velocity_ms=(v_max_kph * 0.6) / 3.6,
        heat_input_w=eng_heat["heat_to_coolant_w"],
    )
    cooling_low = radiator_heat_rejection(
        cooling,
        coolant_temp_c=cooling.thermostat_temp_c + 20,
        ambient_temp_c=ambient_temp_c,
        vehicle_velocity_ms=10.0,
        heat_input_w=eng_heat["heat_to_coolant_w"],
    )
    tit = turbine_inlet_temperature(
        engine_power_hp, boost_psi, displacement_cc,
        air_fuel_ratio=11.8, compression_ratio=compression_ratio,
    )
    ic = intercooler_analysis(boost_psi, 80.0, ambient_temp_c)
    braking = simulate_brake_event(
        vehicle_mass_kg, v_max_kph, 60.0,
        front_disc, rear_disc,
        initial_disc_temp_c=150.0,
        ambient_temp_c=ambient_temp_c,
        brake_fluid=brake_fluid,
    )

    return {
        "engine_power_hp":    engine_power_hp,
        "boost_psi":          boost_psi,
        "ambient_temp_c":     ambient_temp_c,
        "engine_heat":        eng_heat,
        "cooling_highway":    cooling_hwy,
        "cooling_low_speed":  cooling_low,
        "turbo_temperatures": tit,
        "intercooler":        ic,
        "braking":            braking,
        "critical_issues":    _find_critical_issues(cooling_hwy, cooling_low, tit, ic, braking),
    }


def _find_critical_issues(cooling_hwy, cooling_low, tit, ic, brake):
    issues = []
    if cooling_hwy.get("overheat_risk"):
        issues.append("ENGINE OVERHEAT: Radiator insufficient at highway speed")
    if cooling_low.get("overheat_risk"):
        issues.append("ENGINE OVERHEAT: Overheating in traffic — add oil cooler")
    if tit.get("turbine_inlet_temp_c", 0) > 950:
        issues.append(f"TURBO: TIT {tit['turbine_inlet_temp_c']}C — turbine damage risk")
    if brake.get("risk_assessment", {}).get("boiling_risk"):
        issues.append("BRAKES: Fluid boiling risk — upgrade brake fluid immediately")
    if ic.get("knock_risk"):
        issues.append(f"ENGINE: Charge temp {ic['intercooler_outlet_temp_c']}C — knock risk")
    return issues if issues else ["No critical thermal issues identified."]


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Thermodynamics Engine Test")
    print("=" * 60)

    front_disc = BrakeDisc(
        outer_radius_m=0.155, inner_radius_m=0.070,
        thickness_m=0.028, n_vanes=36,
        material_name="Cast Iron (Grey, Brake Grade)"
    )
    rear_disc = BrakeDisc(
        outer_radius_m=0.140, inner_radius_m=0.065,
        thickness_m=0.022, n_vanes=24,
        material_name="Cast Iron (Grey, Brake Grade)"
    )
    cooling = CoolingSystem(
        radiator_area_m2=0.42, n_rows=2,
        has_oil_cooler=True, oil_cooler_area_m2=0.06,
        has_intercooler=True, intercooler_area_m2=0.18,
        intercooler_efficiency=0.88,
        coolant_flow_lpm=90,
    )

    result = full_thermal_analysis(
        engine_power_hp=588,
        boost_psi=22,
        displacement_cc=2998,
        compression_ratio=8.5,
        vehicle_mass_kg=1520,
        cooling=cooling,
        front_disc=front_disc,
        rear_disc=rear_disc,
        v_max_kph=270,
        ambient_temp_c=25.0,
        brake_fluid="Motul RBF660",
    )

    print("\nToyota Supra MK4 — 500whp Build — Full Thermal Analysis")

    print(f"\nEngine heat rejection:")
    print(f"  Total heat:       {result['engine_heat']['heat_rejected_w']/1000:.1f}kW")
    print(f"  To coolant:       {result['engine_heat']['heat_to_coolant_w']/1000:.1f}kW")
    print(f"  To exhaust:       {result['engine_heat']['heat_to_exhaust_w']/1000:.1f}kW")

    cr = result["cooling_highway"]
    print(f"\nCooling (highway):")
    print(f"  Coolant SS temp:  {cr['coolant_steady_state_c']}C")
    print(f"  Overheat risk:    {cr['overheat_risk']}")
    print(f"  {cr['recommendation']}")

    cl = result["cooling_low_speed"]
    print(f"\nCooling (traffic/low speed):")
    print(f"  Coolant SS temp:  {cl['coolant_steady_state_c']}C")
    print(f"  Overheat risk:    {cl['overheat_risk']}")

    tit = result["turbo_temperatures"]
    print(f"\nTurbo temperatures:")
    print(f"  Turbine inlet:    {tit['turbine_inlet_temp_c']}C")
    print(f"  Lambda:           {tit['lambda']}")
    print(f"  Oil coking risk:  {tit['oil_coking_risk']}")
    for rec in tit["recommendations"]:
        print(f"  -> {rec}")

    ic = result["intercooler"]
    print(f"\nIntercooler:")
    print(f"  Compressor out:   {ic['compressor_outlet_temp_c']}C")
    print(f"  IC outlet:        {ic['intercooler_outlet_temp_c']}C")
    print(f"  Temp drop:        {ic['temperature_drop_c']}C")
    print(f"  Power gain:       {ic['estimated_power_gain_pct']}%")
    print(f"  Knock risk:       {ic['knock_risk']}")

    br = result["braking"]
    print(f"\nBraking ({result['v_max_kph'] if 'v_max_kph' in result else 270}kph -> 60kph):")
    print(f"  Total heat:       {br['braking_event']['total_heat_kj']}kJ")
    print(f"  Front disc temp:  {br['temperatures']['front_disc_c']}C")
    print(f"  Rear disc temp:   {br['temperatures']['rear_disc_c']}C")
    print(f"  Boiling risk:     {br['risk_assessment']['boiling_risk']}")
    print(f"  -> {br['risk_assessment']['recommendation']}")

    print(f"\nCritical issues:")
    for issue in result["critical_issues"]:
        symbol = "!" if any(x in issue for x in ["OVERHEAT", "TURBO", "BRAKES", "CRITICAL"]) else "OK"
        print(f"  [{symbol}] {issue}")
