"""
physics_engine/structural.py — Structural Mechanics and Material Selection

Covers:
  1. Basic stress analysis
     - Axial, bending, torsional, shear stress
     - Combined loading (von Mises criterion)
     - Safety factor calculation

  2. Fatigue analysis
     - S-N curve (Wöhler curve) approach
     - Goodman diagram for mean + alternating stress
     - Estimated fatigue life in cycles

  3. Beam/tube analysis
     - Second moment of area for common sections
     - Deflection under load
     - Buckling load (Euler column buckling)
     - Roll cage tube sizing

  4. Aero surface structural analysis
     - Wing/splitter panel stress under aerodynamic load
     - Composite panel sizing
     - Sandwich panel analysis

  5. Material selection optimizer
     - Minimum weight design for stress requirements
     - Cost-constrained material selection

All units SI:
  Force:    N
  Stress:   Pa (use MPa for display)
  Length:   m
  Moment:   N·m
  Area:     m²
  Section modulus: m³

References:
  - Roark's Formulas for Stress and Strain (8th ed.)
  - Shigley's Mechanical Engineering Design
  - Ashby, M.F. "Materials Selection in Mechanical Design"
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from materials_db import MATERIALS, Material, get_material

# ── Cross section properties ───────────────────────────────────────────────────

@dataclass
class CrossSection:
    """
    Geometric properties of a cross-section.
    All in SI (m, m², m⁴, m³).
    """
    area_m2:            float    # cross-sectional area
    I_xx_m4:            float    # second moment of area about x-axis (bending)
    I_yy_m4:            float    # second moment of area about y-axis
    J_m4:               float    # polar moment of area (torsion)
    y_max_m:            float    # distance from neutral axis to extreme fibre
    x_max_m:            float    # same for y-axis
    perimeter_m:        float    # outer perimeter (for paint/coating area)
    section_name:       str = "" # description

    @property
    def Z_xx_m3(self) -> float:
        """Section modulus about x-axis: Z = I/y"""
        return self.I_xx_m4 / self.y_max_m if self.y_max_m > 0 else 0

    @property
    def Z_yy_m3(self) -> float:
        return self.I_yy_m4 / self.x_max_m if self.x_max_m > 0 else 0

    @property
    def r_xx_m(self) -> float:
        """Radius of gyration about x-axis: r = sqrt(I/A)"""
        return np.sqrt(self.I_xx_m4 / self.area_m2) if self.area_m2 > 0 else 0

    def summary(self) -> dict:
        return {
            "section":      self.section_name,
            "area_mm2":     round(self.area_m2 * 1e6, 2),
            "I_xx_mm4":     round(self.I_xx_m4 * 1e12, 1),
            "Z_xx_mm3":     round(self.Z_xx_m3 * 1e9, 2),
            "r_xx_mm":      round(self.r_xx_m * 1000, 2),
            "J_mm4":        round(self.J_m4 * 1e12, 1),
        }


def circular_tube(outer_dia_mm: float, wall_mm: float) -> CrossSection:
    """Hollow circular tube — roll cage tubing standard."""
    D  = outer_dia_mm / 1000.0
    d  = (outer_dia_mm - 2 * wall_mm) / 1000.0
    A  = np.pi / 4 * (D**2 - d**2)
    I  = np.pi / 64 * (D**4 - d**4)
    J  = np.pi / 32 * (D**4 - d**4)
    return CrossSection(
        area_m2=A, I_xx_m4=I, I_yy_m4=I, J_m4=J,
        y_max_m=D/2, x_max_m=D/2,
        perimeter_m=np.pi * D,
        section_name=f"Tube {outer_dia_mm}×{wall_mm}mm",
    )


def solid_circle(dia_mm: float) -> CrossSection:
    """Solid circular section — shaft, rod."""
    D = dia_mm / 1000.0
    A = np.pi / 4 * D**2
    I = np.pi / 64 * D**4
    J = np.pi / 32 * D**4
    return CrossSection(
        area_m2=A, I_xx_m4=I, I_yy_m4=I, J_m4=J,
        y_max_m=D/2, x_max_m=D/2,
        perimeter_m=np.pi * D,
        section_name=f"Solid circle {dia_mm}mm",
    )


def rectangular_tube(width_mm: float, height_mm: float, wall_mm: float) -> CrossSection:
    """Rectangular hollow section (RHS) — chassis rails, subframe."""
    b  = width_mm  / 1000.0
    h  = height_mm / 1000.0
    t  = wall_mm   / 1000.0
    bi = b - 2*t
    hi = h - 2*t
    A  = b*h - bi*hi
    Ixx = (b*h**3 - bi*hi**3) / 12
    Iyy = (h*b**3 - hi*bi**3) / 12
    # Torsion — thin-walled approximation (Bredt formula)
    Am = (b - t) * (h - t)  # enclosed area
    J  = 4 * Am**2 / (2 * ((b-t)/t + (h-t)/t))
    return CrossSection(
        area_m2=A, I_xx_m4=Ixx, I_yy_m4=Iyy, J_m4=J,
        y_max_m=h/2, x_max_m=b/2,
        perimeter_m=2*(b+h),
        section_name=f"RHS {width_mm}×{height_mm}×{wall_mm}mm",
    )


def flat_plate(width_mm: float, thickness_mm: float) -> CrossSection:
    """Flat plate section — splitter, wing panel."""
    b = width_mm    / 1000.0
    t = thickness_mm / 1000.0
    A  = b * t
    Ixx = b * t**3 / 12
    Iyy = t * b**3 / 12
    J   = b * t**3 / 3   # open section approximation
    return CrossSection(
        area_m2=A, I_xx_m4=Ixx, I_yy_m4=Iyy, J_m4=J,
        y_max_m=t/2, x_max_m=b/2,
        perimeter_m=2*(b+t),
        section_name=f"Plate {width_mm}×{thickness_mm}mm",
    )


# ── Stress calculations ───────────────────────────────────────────────────────

def axial_stress(force_n: float, section: CrossSection) -> float:
    """σ_axial = F / A"""
    return force_n / section.area_m2


def bending_stress(moment_nm: float, section: CrossSection) -> float:
    """σ_bending = M / Z = M × y / I"""
    return moment_nm / section.Z_xx_m3 if section.Z_xx_m3 > 0 else 0


def torsional_shear_stress(torque_nm: float, section: CrossSection) -> float:
    """τ_torsion = T × r / J"""
    if section.J_m4 <= 0:
        return 0
    return torque_nm * section.y_max_m / section.J_m4


def transverse_shear_stress(shear_n: float, section: CrossSection) -> float:
    """τ_shear = V × Q / (I × b) — simplified as V / A × 1.5 for rect, 2.0 for circle."""
    return 1.5 * shear_n / section.area_m2


def von_mises_stress(sigma_x: float, sigma_y: float = 0.0,
                      tau_xy: float = 0.0) -> float:
    """
    Von Mises equivalent stress for combined loading.
    σ_vm = sqrt(σ_x² - σ_x×σ_y + σ_y² + 3τ_xy²)

    This is the yield criterion — failure when σ_vm ≥ σ_yield.
    """
    return np.sqrt(sigma_x**2 - sigma_x*sigma_y + sigma_y**2 + 3*tau_xy**2)


def safety_factor(applied_stress_pa: float, material_name: str,
                   stress_type: str = "yield") -> dict:
    """
    Calculate safety factor for a given stress and material.
    SF = σ_material / σ_applied

    Args:
        applied_stress_pa: Actual stress in component (Pa)
        material_name:     Material from database
        stress_type:       'yield' | 'ultimate' | 'fatigue'

    Returns:
        Safety factor analysis dict
    """
    mat = get_material(material_name)
    if not mat:
        return {"error": f"Material not found: {material_name}"}

    if stress_type == "yield":
        strength = mat.yield_strength_pa
    elif stress_type == "ultimate":
        strength = mat.ultimate_strength_pa
    elif stress_type == "fatigue":
        strength = mat.fatigue_limit_pa or mat.yield_strength_pa * 0.4
    else:
        strength = mat.yield_strength_pa

    sf = strength / max(applied_stress_pa, 1.0)

    if sf >= 3.0:
        assessment = "overdesigned — weight reduction opportunity"
    elif sf >= 2.0:
        assessment = "conservative — good for safety-critical parts"
    elif sf >= 1.5:
        assessment = "adequate — typical engineering design"
    elif sf >= 1.0:
        assessment = "marginal — reduce load or upgrade material"
    else:
        assessment = "FAILURE — applied stress exceeds material strength"

    return {
        "applied_stress_mpa":  round(applied_stress_pa / 1e6, 2),
        "material_strength_mpa": round(strength / 1e6, 2),
        "safety_factor":       round(sf, 3),
        "assessment":          assessment,
        "material":            material_name,
        "stress_type":         stress_type,
    }


# ── Beam analysis ─────────────────────────────────────────────────────────────

def beam_max_bending_moment(force_n: float, length_m: float,
                              support: str = "simply_supported",
                              load: str = "point_center") -> float:
    """
    Calculate maximum bending moment for common beam configurations.

    support: 'simply_supported' | 'cantilever' | 'fixed_both'
    load:    'point_center' | 'point_end' | 'distributed'

    Returns: Maximum bending moment (N·m)
    """
    L = length_m
    F = force_n

    cases = {
        ("simply_supported", "point_center"):   F * L / 4,
        ("simply_supported", "distributed"):    F * L / 8,
        ("cantilever",       "point_end"):      F * L,
        ("cantilever",       "distributed"):    F * L / 2,
        ("fixed_both",       "point_center"):   F * L / 8,
        ("fixed_both",       "distributed"):    F * L / 12,
    }
    return cases.get((support, load), F * L / 4)


def beam_deflection(force_n: float, length_m: float,
                     section: CrossSection, material_name: str,
                     support: str = "simply_supported",
                     load: str = "point_center") -> dict:
    """
    Calculate beam deflection and check against typical limits.

    Returns: Deflection analysis dict
    """
    mat = get_material(material_name)
    E   = mat.elastic_modulus_pa if mat else 200e9
    I   = section.I_xx_m4
    L   = length_m
    F   = force_n
    EI  = E * I

    deflection_cases = {
        ("simply_supported", "point_center"):   F * L**3 / (48 * EI),
        ("simply_supported", "distributed"):    5 * F * L**3 / (384 * EI),
        ("cantilever",       "point_end"):      F * L**3 / (3 * EI),
        ("cantilever",       "distributed"):    F * L**4 / (8 * EI * L),
        ("fixed_both",       "point_center"):   F * L**3 / (192 * EI),
        ("fixed_both",       "distributed"):    F * L**4 / (384 * EI * L),
    }
    delta = deflection_cases.get((support, load), F * L**3 / (48 * EI))

    # Typical serviceability limits
    limit_general  = L / 300    # general structural: L/300
    limit_aero     = L / 1000   # aero surface: L/1000
    limit_chassis  = L / 500    # chassis member: L/500

    return {
        "deflection_mm":     round(delta * 1000, 3),
        "span_mm":           round(L * 1000, 0),
        "deflection_ratio":  round(L / delta, 0) if delta > 0 else float("inf"),
        "within_general":    delta <= limit_general,
        "within_aero":       delta <= limit_aero,
        "within_chassis":    delta <= limit_chassis,
        "elastic_modulus_gpa": round(E / 1e9, 1),
        "EI_nm2":            round(EI, 2),
    }


def euler_buckling_load(section: CrossSection, length_m: float,
                          material_name: str,
                          end_condition: str = "pinned_pinned") -> dict:
    """
    Euler critical buckling load for slender columns.
    P_cr = π² × E × I / (K × L)²

    End conditions (K factor):
      pinned_pinned:   K = 1.0  (both ends free to rotate)
      fixed_pinned:    K = 0.7
      fixed_fixed:     K = 0.5
      fixed_free:      K = 2.0  (flagpole — worst case)

    Args:
        section:        Cross-section properties
        length_m:       Member length
        material_name:  Material for elastic modulus
        end_condition:  Boundary condition string

    Returns:
        Buckling analysis dict
    """
    K_factors = {
        "pinned_pinned": 1.0,
        "fixed_pinned":  0.7,
        "fixed_fixed":   0.5,
        "fixed_free":    2.0,
    }
    K   = K_factors.get(end_condition, 1.0)
    mat = get_material(material_name)
    E   = mat.elastic_modulus_pa if mat else 200e9
    I   = section.I_xx_m4
    L   = length_m

    P_cr = (np.pi**2 * E * I) / (K * L)**2

    # Slenderness ratio — indicates if Euler buckling is valid
    # (Euler valid when SR > ~100 for steel)
    r    = section.r_xx_m
    SR   = (K * L) / r if r > 0 else float("inf")

    euler_valid = SR > 80   # approximately

    return {
        "critical_buckling_load_n":  round(P_cr),
        "critical_buckling_load_kn": round(P_cr / 1000, 2),
        "slenderness_ratio":         round(SR, 1),
        "euler_valid":               euler_valid,
        "end_condition":             end_condition,
        "K_factor":                  K,
        "note": ("Euler buckling valid — slender column"
                 if euler_valid else
                 "Low slenderness — material yielding will govern before buckling"),
    }


# ── Fatigue analysis ──────────────────────────────────────────────────────────

def sn_curve_life(stress_amplitude_pa: float, material_name: str,
                   mean_stress_pa: float = 0.0,
                   stress_concentration: float = 1.0) -> dict:
    """
    Estimate fatigue life using S-N curve approach with Goodman correction.

    Goodman diagram for mean stress correction:
    σ_a / S_e + σ_m / S_u = 1/SF

    where:
      σ_a = stress amplitude (half the stress range)
      σ_m = mean stress
      S_e = endurance limit
      S_u = ultimate strength
      SF  = safety factor

    Modified Goodman: σ_a_eff = σ_a / (1 - σ_m/S_u)

    Args:
        stress_amplitude_pa:  Half of peak-to-peak stress range (Pa)
        material_name:        Material
        mean_stress_pa:       Mean stress (0 = fully reversed, tension = positive)
        stress_concentration: Kt — stress concentration factor at notch/weld

    Returns:
        Fatigue life analysis dict
    """
    mat = get_material(material_name)
    if not mat:
        return {"error": f"Material not found: {material_name}"}

    S_u = mat.ultimate_strength_pa
    S_y = mat.yield_strength_pa
    S_e = mat.fatigue_limit_pa or S_u * 0.4   # estimate if not in DB

    # Apply stress concentration
    sigma_a = stress_amplitude_pa * stress_concentration
    sigma_m = mean_stress_pa

    # Goodman correction for mean stress
    if sigma_m >= S_u:
        return {
            "cycles_to_failure": 0,
            "life_assessment":   "STATIC FAILURE — mean stress exceeds ultimate strength",
        }

    sigma_a_eff = sigma_a / (1.0 - sigma_m / S_u) if sigma_m < S_u else sigma_a

    # S-N curve life estimation
    # For steel: N = (S_e / σ_a)^b × 10^6 where b ≈ -0.1 (slope)
    # For Al: no true endurance limit — use 10^7 cycle limit
    b = -0.1   # S-N slope (typical for steel)

    if sigma_a_eff <= 0:
        cycles = float("inf")
    elif sigma_a_eff < S_e:
        cycles = float("inf")  # below endurance limit = infinite life
    else:
        # Basquin's law: σ_a = σ_f' × (2N)^b
        # Approximate: N = 10^6 × (S_e / σ_a_eff)^(1/b_slope)
        b_slope = 0.085  # typical for steels
        ratio   = S_e / sigma_a_eff
        if ratio <= 0:
            cycles = 0
        else:
            cycles = 1e6 * (ratio ** (1.0 / b_slope))

    # Goodman safety factor
    sf_goodman = (S_e / sigma_a_eff) * (1 - sigma_m / S_u) if sigma_a_eff > 0 else float("inf")

    if cycles == float("inf"):
        life_str = "Infinite life (below endurance limit)"
        assessment = "safe"
    elif cycles > 1e9:
        life_str = f"{cycles:.2e} cycles (very long life)"
        assessment = "safe"
    elif cycles > 1e6:
        life_str = f"{cycles/1e6:.1f} million cycles"
        assessment = "adequate"
    elif cycles > 1e4:
        life_str = f"{cycles/1000:.0f}k cycles"
        assessment = "limited life — monitor and replace"
    else:
        life_str = f"{int(cycles)} cycles"
        assessment = "IMMINENT FAILURE — redesign required"

    return {
        "stress_amplitude_mpa":    round(stress_amplitude_pa / 1e6, 2),
        "mean_stress_mpa":         round(mean_stress_pa / 1e6, 2),
        "effective_amplitude_mpa": round(sigma_a_eff / 1e6, 2),
        "endurance_limit_mpa":     round(S_e / 1e6, 2),
        "ultimate_strength_mpa":   round(S_u / 1e6, 2),
        "stress_concentration_kt": stress_concentration,
        "cycles_to_failure":       cycles,
        "life_estimate":           life_str,
        "goodman_sf":              round(sf_goodman, 3),
        "assessment":              assessment,
        "material":                material_name,
    }


# ── Aero surface structural analysis ─────────────────────────────────────────

def aero_panel_stress(pressure_pa: float, panel_width_m: float,
                       panel_length_m: float, panel_thickness_m: float,
                       material_name: str,
                       support: str = "simply_supported") -> dict:
    """
    Stress analysis for an aero panel (wing, splitter, diffuser) under
    aerodynamic pressure loading.

    Treats panel as a simply supported or fixed plate under uniform pressure.
    Uses Roark's plate formula for rectangular plates.

    Args:
        pressure_pa:       Aerodynamic pressure (Pa) — downforce / area
        panel_width_m:     Short dimension of panel (m)
        panel_length_m:    Long dimension of panel (m)
        panel_thickness_m: Panel thickness (m)
        material_name:     Panel material
        support:           'simply_supported' | 'fixed'

    Returns:
        Stress analysis dict
    """
    mat = get_material(material_name)
    if not mat:
        return {"error": f"Material not found: {material_name}"}

    b = min(panel_width_m, panel_length_m)   # short side
    a = max(panel_width_m, panel_length_m)   # long side
    t = panel_thickness_m
    q = pressure_pa   # uniform pressure (Pa = N/m²)
    E = mat.elastic_modulus_pa
    nu = mat.poisson_ratio

    # Roark's plate formula — maximum stress and deflection
    # For simply supported rectangular plate under uniform load:
    # σ_max = β × q × b² / t²
    # δ_max = α × q × b⁴ / (E × t³)

    aspect = a / b

    # Interpolate β and α from Roark's Table 11.4 (simply supported)
    # Tabulated values for a/b = 1.0, 1.5, 2.0, 3.0, ∞
    if support == "simply_supported":
        beta_table  = {1.0: 0.2874, 1.5: 0.4167, 2.0: 0.4671, 3.0: 0.5138, 5.0: 0.5425}
        alpha_table = {1.0: 0.0443, 1.5: 0.0843, 2.0: 0.1106, 3.0: 0.1336, 5.0: 0.1400}
    else:  # fixed edges
        beta_table  = {1.0: 0.1386, 1.5: 0.1794, 2.0: 0.1985, 3.0: 0.2098, 5.0: 0.2184}
        alpha_table = {1.0: 0.0138, 1.5: 0.0243, 2.0: 0.0309, 3.0: 0.0369, 5.0: 0.0399}

    # Find nearest tabulated values
    keys = sorted(beta_table.keys())
    ar   = min(max(aspect, keys[0]), keys[-1])
    # Linear interpolation
    for i in range(len(keys)-1):
        if keys[i] <= ar <= keys[i+1]:
            t1, t2 = keys[i], keys[i+1]
            f = (ar - t1) / (t2 - t1)
            beta  = beta_table[t1]  + f * (beta_table[t2]  - beta_table[t1])
            alpha = alpha_table[t1] + f * (alpha_table[t2] - alpha_table[t1])
            break
    else:
        beta  = beta_table[keys[-1]]
        alpha = alpha_table[keys[-1]]

    # Maximum stress (at centre of long side)
    sigma_max = beta * q * b**2 / t**2

    # Maximum deflection (at centre)
    delta_max = alpha * q * b**4 / (E * t**3)

    # Safety factor
    sf = mat.yield_strength_pa / sigma_max

    return {
        "panel_dimensions":      f"{round(panel_width_m*1000)}×{round(panel_length_m*1000)}×{round(t*1000,1)}mm",
        "material":              material_name,
        "pressure_pa":           round(pressure_pa, 2),
        "max_stress_mpa":        round(sigma_max / 1e6, 2),
        "yield_strength_mpa":    round(mat.yield_strength_pa / 1e6, 2),
        "safety_factor":         round(sf, 2),
        "max_deflection_mm":     round(delta_max * 1000, 3),
        "deflection_ratio":      round(b / delta_max, 0) if delta_max > 0 else float("inf"),
        "aspect_ratio":          round(aspect, 2),
        "support_condition":     support,
        "will_yield":            sigma_max >= mat.yield_strength_pa,
        "recommendation":        _panel_recommendation(sf, delta_max, b),
    }


def _panel_recommendation(sf: float, deflection: float, span: float) -> str:
    if sf < 1.0:
        return "FAILURE: Increase thickness, add ribs, or use stronger material."
    elif sf < 1.5:
        return "Marginal: Increase thickness by 50% or add stiffening ribs."
    elif sf < 2.0:
        return "Adequate for racing. Monitor for cracking at attachments."
    elif deflection > span / 200:
        return f"Stress OK but excessive deflection. Add spanwise ribs or increase thickness."
    else:
        return "Structure adequate. Good margin."


def size_for_stress(required_sf: float, load_n: float, length_m: float,
                     material_name: str, section_type: str = "tube",
                     load_type: str = "bending") -> dict:
    """
    Reverse design — find minimum section size to meet safety factor.

    Args:
        required_sf:   Required safety factor
        load_n:        Applied force (N)
        length_m:      Member length (m)
        material_name: Material
        section_type:  'tube' | 'rhs' | 'plate'
        load_type:     'bending' | 'axial' | 'buckling'

    Returns:
        Minimum section dimensions
    """
    mat = get_material(material_name)
    if not mat:
        return {"error": f"Material not found: {material_name}"}

    allowable_stress = mat.yield_strength_pa / required_sf

    if load_type == "axial":
        # σ = F/A → A = F/σ_allow
        area_needed = load_n / allowable_stress
        # For circular tube with wall = 10% OD
        D = np.sqrt(4 * area_needed / (np.pi * (1 - 0.64)))   # 0.8 OD inner
        wall = D * 0.10
        return {
            "required_area_mm2":   round(area_needed * 1e6, 1),
            "suggested_tube":      f"{round(D*1000)}×{round(wall*1000, 1)}mm",
            "outer_dia_mm":        round(D * 1000),
            "wall_mm":             round(wall * 1000, 1),
            "actual_sf":           required_sf,
        }

    elif load_type == "bending":
        M = beam_max_bending_moment(load_n, length_m, "cantilever", "point_end")
        Z_needed = M / allowable_stress
        # For circular tube: Z = π/32 × (D⁴ - d⁴) / (D/2)
        # Approximate with solid: D ≈ (32Z/π)^(1/3)
        D_solid = (32 * Z_needed / np.pi) ** (1/3)
        D_tube  = D_solid * 1.3   # tube needs to be larger
        wall    = D_tube * 0.10
        section = circular_tube(D_tube * 1000, wall * 1000)
        actual_M = bending_stress(M, section)
        actual_sf = mat.yield_strength_pa / actual_M if actual_M > 0 else float("inf")
        return {
            "required_Z_mm3":   round(Z_needed * 1e9, 2),
            "bending_moment_nm":round(M, 1),
            "suggested_tube":   f"{round(D_tube*1000)}×{round(wall*1000, 1)}mm OD",
            "outer_dia_mm":     round(D_tube * 1000),
            "wall_mm":          round(wall * 1000, 1),
            "actual_sf":        round(actual_sf, 2),
        }

    elif load_type == "buckling":
        # P_cr = π²EI/(KL)² → I = P_cr × (KL)² / (π²E)
        K       = 1.0  # pinned-pinned
        I_needed = load_n * required_sf * (K * length_m)**2 / (np.pi**2 * mat.elastic_modulus_pa)
        D       = (64 * I_needed / np.pi) ** (1/4) * 1.3
        wall    = D * 0.10
        return {
            "required_I_mm4":   round(I_needed * 1e12, 1),
            "suggested_tube":   f"{round(D*1000)}×{round(wall*1000, 1)}mm OD",
            "outer_dia_mm":     round(D * 1000),
            "wall_mm":          round(wall * 1000, 1),
        }

    return {"error": f"Unknown load type: {load_type}"}


# ── Roll cage analysis ────────────────────────────────────────────────────────

def analyse_roll_cage_tube(outer_dia_mm: float, wall_mm: float,
                            length_m: float, material_name: str,
                            load_n: float = 50000.0) -> dict:
    """
    Analyse a roll cage tube for:
    - Bending strength (side impact load)
    - Axial buckling (roof crush load)
    - Safety factors

    FIA minimum: 38×2.5mm chromoly (4130) or 40×2.0mm

    Args:
        outer_dia_mm: Tube outer diameter (mm)
        wall_mm:      Wall thickness (mm)
        length_m:     Unsupported length (m)
        material_name:Material
        load_n:       Design load (N) — 50kN typical for roll hoop

    Returns:
        Structural analysis dict
    """
    section = circular_tube(outer_dia_mm, wall_mm)
    mat     = get_material(material_name)

    if not mat:
        return {"error": f"Material not found: {material_name}"}

    # Bending analysis (side load — fixed-fixed beam approximation for roll hoop)
    M         = load_n * length_m / 8.0   # fixed-fixed point load = FL/8
    sigma_b   = bending_stress(M, section)
    sf_bending = mat.yield_strength_pa / sigma_b if sigma_b > 0 else float("inf")

    # Axial buckling (roof crush)
    buckle = euler_buckling_load(section, length_m, material_name, "fixed_pinned")
    sf_buckle = buckle["critical_buckling_load_n"] / load_n

    # Fatigue (vibration loading — assume 30% of static as alternating)
    sigma_alt = sigma_b * 0.30
    fatigue   = sn_curve_life(sigma_alt, material_name, sigma_b * 0.70, 1.5)

    # FIA compliance check
    # Main hoop: min 38×2.5mm 4130 chromoly
    fia_min_area = circular_tube(38, 2.5).area_m2
    fia_ok = (section.area_m2 >= fia_min_area and
              "Chromoly" in material_name or "4340" in material_name)

    return {
        "tube_size":          f"{outer_dia_mm}×{wall_mm}mm",
        "material":           material_name,
        "section":            section.summary(),

        "bending": {
            "design_load_n":       load_n,
            "bending_moment_nm":   round(M, 1),
            "max_stress_mpa":      round(sigma_b / 1e6, 2),
            "yield_strength_mpa":  round(mat.yield_strength_pa / 1e6, 2),
            "safety_factor":       round(sf_bending, 2),
            "passes":              sf_bending >= 1.5,
        },

        "buckling": {
            "critical_load_kn":  buckle["critical_buckling_load_kn"],
            "safety_factor":     round(sf_buckle, 2),
            "slenderness_ratio": buckle["slenderness_ratio"],
            "passes":            sf_buckle >= 2.0,
        },

        "fatigue": {
            "life_estimate":     fatigue.get("life_estimate", "N/A"),
            "goodman_sf":        fatigue.get("goodman_sf", 0),
        },

        "fia_compliance":      fia_ok,
        "mass_per_metre_kg":   round(section.area_m2 * mat.density_kg_m3, 3),
        "overall_pass":        sf_bending >= 1.5 and sf_buckle >= 2.0,
    }


# ── Lightweight material optimizer ────────────────────────────────────────────

def optimize_material(required_yield_mpa: float, load_n: float,
                       length_m: float, load_type: str = "bending",
                       max_cost_usd_kg: float = None,
                       optimize_for: str = "weight") -> List[dict]:
    """
    Find optimal material and minimum section for a structural requirement.
    Compares materials by weight efficiency.

    Args:
        required_yield_mpa: Minimum yield strength needed (MPa)
        load_n:             Applied load (N)
        length_m:           Member length (m)
        load_type:          'bending' | 'axial' | 'buckling'
        max_cost_usd_kg:    Maximum material cost (None = no limit)
        optimize_for:       'weight' | 'cost' | 'stiffness'

    Returns:
        Ranked list of material + section combinations
    """
    results = []

    for mat_name, mat in MATERIALS.items():
        if max_cost_usd_kg and mat.cost_usd_per_kg > max_cost_usd_kg:
            continue
        if mat.yield_strength_pa < required_yield_mpa * 1e6 * 0.5:
            continue   # too weak — skip

        sizing = size_for_stress(2.0, load_n, length_m, mat_name, "tube", load_type)
        if "error" in sizing:
            continue

        OD   = sizing.get("outer_dia_mm", 50)
        wall = sizing.get("wall_mm", 3)
        section = circular_tube(OD, wall)

        tube_mass_per_m = section.area_m2 * mat.density_kg_m3
        tube_cost_per_m = tube_mass_per_m * mat.cost_usd_per_kg

        results.append({
            "material":          mat_name,
            "tube_size":         sizing.get("suggested_tube", ""),
            "mass_kg_per_m":     round(tube_mass_per_m, 4),
            "cost_usd_per_m":    round(tube_cost_per_m, 3),
            "specific_strength": round(mat.specific_strength / 1e3, 1),
            "safety_factor":     sizing.get("actual_sf", 2.0),
            "density_kg_m3":     mat.density_kg_m3,
            "yield_mpa":         round(mat.yield_strength_pa / 1e6, 0),
            "cost_usd_kg":       mat.cost_usd_per_kg,
        })

    sort_key = {
        "weight":    lambda r: r["mass_kg_per_m"],
        "cost":      lambda r: r["cost_usd_per_m"],
        "stiffness": lambda r: -MATERIALS[r["material"]].elastic_modulus_pa,
    }.get(optimize_for, lambda r: r["mass_kg_per_m"])

    results.sort(key=sort_key)
    return results[:8]


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Structural Analysis Test")
    print("=" * 60)

    # Roll cage tube analysis
    print("\nRoll cage tube comparison:")
    for outer_dia, wall, mat_name in [
        (38, 2.5, "Chromoly Steel (4130)"),
        (40, 2.0, "Chromoly Steel (4130)"),
        (45, 3.0, "High Strength Steel (AISI 4340)"),
    ]:
        r = analyse_roll_cage_tube(outer_dia, wall, 1.2, mat_name, load_n=5000)
        print(f"  {r['tube_size']:15} {mat_name:40} "
              f"SF_bend={r['bending']['safety_factor']:.2f}  "
              f"SF_buckle={r['buckling']['safety_factor']:.2f}  "
              f"FIA={'✓' if r['fia_compliance'] else '✗'}  "
              f"{r['mass_per_metre_kg']}kg/m")

    # Wing panel stress analysis
    print("\nRear wing panel stress (200kph, 45kg downforce):")
    force_n   = 45 * 9.81
    area_m2   = 1.4 * 0.25  # 1400mm span × 250mm chord
    pressure  = force_n / area_m2

    for mat in ["Carbon Fibre UD Prepreg (T700/Epoxy)",
                "Aluminium 6061-T6",
                "Fibreglass (E-Glass/Epoxy)"]:
        r = aero_panel_stress(pressure, 0.25, 1.4, 0.003, mat)
        if "error" not in r:
            print(f"  {mat:45} σ={r['max_stress_mpa']:6.1f}MPa  "
                  f"SF={r['safety_factor']:5.2f}  "
                  f"δ={r['max_deflection_mm']:.2f}mm  "
                  f"{'PASS' if not r['will_yield'] else 'FAIL'}")

    # Material optimizer
    print("\nLightest material for 500N bending load, 800mm span, SF≥2:")
    results = optimize_material(100, 500, 0.8, "bending", optimize_for="weight")
    for r in results[:5]:
        print(f"  {r['material']:45} {r['tube_size']:20} "
              f"{r['mass_kg_per_m']:.4f}kg/m  ${r['cost_usd_per_m']:.2f}/m")

    # Fatigue analysis
    print("\nFatigue life — suspension arm under 300MPa alternating stress:")
    for mat in ["Chromoly Steel (4130)", "Aluminium 7075-T6", "Titanium Grade 5 (Ti-6Al-4V)"]:
        f = sn_curve_life(300e6, mat, mean_stress_pa=100e6, stress_concentration=1.8)
        if "error" not in f:
            print(f"  {mat:45} {f['life_estimate']}")
