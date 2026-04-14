"""
physics_engine/materials_db.py — Material Properties Database

All properties in SI units unless noted.
Temperature-dependent properties stored as lookup tables.
References: Ashby Materials Selection, Roark's Formulas, MIL-HDBK-5.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple


# ── Material dataclass ────────────────────────────────────────────────────────

@dataclass
class Material:
    """
    Full material property set for structural, thermal, and aero analysis.
    All SI units:
      Stress/Modulus: Pa (Pascal)
      Density:        kg/m³
      Thermal:        W/(m·K), J/(kg·K), K
      Cost:           USD/kg (approximate, 2024)
    """
    name:               str
    category:           str          # metal | composite | polymer | ceramic

    # ── Mechanical ────────────────────────────────────────────────────────────
    density_kg_m3:      float        # kg/m³
    elastic_modulus_pa: float        # Young's modulus E (Pa)
    shear_modulus_pa:   float        # G (Pa)
    poisson_ratio:      float        # dimensionless
    yield_strength_pa:  float        # σ_y (Pa) — onset of plastic deformation
    ultimate_strength_pa: float      # σ_u (Pa) — fracture point
    fatigue_limit_pa:   Optional[float] = None
    elongation_pct:     float = 0.0
    hardness_vickers:   Optional[float] = None

    # ── Thermal ───────────────────────────────────────────────────────────────
    thermal_conductivity_w_mk:  float = 0.0
    specific_heat_j_kgk:       float = 0.0
    thermal_expansion_per_k:   float = 0.0
    max_service_temp_k:         float = 0.0
    melting_point_k:            Optional[float] = None

    # ── Cost & availability ───────────────────────────────────────────────────
    cost_usd_per_kg:    float = 0.0
    machinability:      str = "good"
    weldability:        str = "good"
    formability:        str = "good"
    corrosion_resistance: str = "moderate"
    notes:              str = ""
    common_uses:        List[str] = field(default_factory=list)

    @property
    def specific_stiffness(self) -> float:
        return self.elastic_modulus_pa / self.density_kg_m3

    @property
    def specific_strength(self) -> float:
        return self.yield_strength_pa / self.density_kg_m3

    @property
    def thermal_diffusivity_m2_s(self) -> float:
        if self.specific_heat_j_kgk == 0 or self.density_kg_m3 == 0:
            return 0.0
        return self.thermal_conductivity_w_mk / (self.density_kg_m3 * self.specific_heat_j_kgk)

    def stress_at_temp(self, temp_k: float) -> float:
        if not self.melting_point_k or temp_k <= 293:
            return self.yield_strength_pa
        ratio = temp_k / self.melting_point_k
        if ratio < 0.4:
            return self.yield_strength_pa
        degradation = 1.0 - (ratio - 0.4) / 0.6
        return max(0.0, self.yield_strength_pa * degradation)

    def summary(self) -> dict:
        return {
            "name":               self.name,
            "category":           self.category,
            "density_kg_m3":      self.density_kg_m3,
            "yield_strength_mpa": round(self.yield_strength_pa / 1e6, 1),
            "elastic_modulus_gpa":round(self.elastic_modulus_pa / 1e9, 1),
            "specific_strength":  round(self.specific_strength / 1e3, 1),
            "specific_stiffness": round(self.specific_stiffness / 1e3, 1),
            "max_service_temp_c": round(self.max_service_temp_k - 273.15, 0),
            "cost_usd_per_kg":    self.cost_usd_per_kg,
        }


# ── Material database ─────────────────────────────────────────────────────────

MATERIALS: Dict[str, Material] = {}

def _add(m: Material):
    MATERIALS[m.name] = m
    return m


# ── Steels ────────────────────────────────────────────────────────────────────

_add(Material(
    name="Mild Steel (AISI 1020)", category="metal",
    density_kg_m3=7870, elastic_modulus_pa=200e9, shear_modulus_pa=80e9,
    poisson_ratio=0.29, yield_strength_pa=210e6, ultimate_strength_pa=380e6,
    fatigue_limit_pa=190e6, elongation_pct=36, hardness_vickers=131,
    thermal_conductivity_w_mk=51.9, specific_heat_j_kgk=486,
    thermal_expansion_per_k=11.7e-6, max_service_temp_k=673, melting_point_k=1803,
    cost_usd_per_kg=0.8, machinability="excellent", weldability="excellent",
    formability="excellent", corrosion_resistance="poor",
    notes="Common structural steel. Rusts without protection.",
    common_uses=["chassis", "subframe", "body panels (budget)"],
))

_add(Material(
    name="High Strength Steel (AISI 4340)", category="metal",
    density_kg_m3=7850, elastic_modulus_pa=205e9, shear_modulus_pa=80e9,
    poisson_ratio=0.28, yield_strength_pa=470e6, ultimate_strength_pa=745e6,
    fatigue_limit_pa=380e6, elongation_pct=22, hardness_vickers=217,
    thermal_conductivity_w_mk=44.5, specific_heat_j_kgk=475,
    thermal_expansion_per_k=12.3e-6, max_service_temp_k=723, melting_point_k=1703,
    cost_usd_per_kg=2.5, machinability="good", weldability="good",
    corrosion_resistance="poor",
    notes="Alloy steel. Suspension components, driveshafts, crankshafts.",
    common_uses=["connecting rods", "crankshaft", "driveshaft", "roll cage"],
))

_add(Material(
    name="Chromoly Steel (4130)", category="metal",
    density_kg_m3=7850, elastic_modulus_pa=205e9, shear_modulus_pa=80e9,
    poisson_ratio=0.29, yield_strength_pa=435e6, ultimate_strength_pa=670e6,
    fatigue_limit_pa=310e6, elongation_pct=25.5, hardness_vickers=197,
    thermal_conductivity_w_mk=42.7, specific_heat_j_kgk=477,
    thermal_expansion_per_k=12.3e-6, max_service_temp_k=700, melting_point_k=1703,
    cost_usd_per_kg=3.2, machinability="good", weldability="good",
    corrosion_resistance="poor",
    notes="Chromium-molybdenum alloy steel. Roll cage and chassis tubing standard.",
    common_uses=["roll cage", "chassis tubes", "suspension arms", "turbo manifold"],
))

_add(Material(
    name="Ultra High Strength Steel (DOCOL 1700M)", category="metal",
    density_kg_m3=7800, elastic_modulus_pa=207e9, shear_modulus_pa=80e9,
    poisson_ratio=0.29, yield_strength_pa=1400e6, ultimate_strength_pa=1700e6,
    fatigue_limit_pa=700e6, elongation_pct=5, hardness_vickers=490,
    thermal_conductivity_w_mk=35, specific_heat_j_kgk=480,
    thermal_expansion_per_k=11.5e-6, max_service_temp_k=673, melting_point_k=1773,
    cost_usd_per_kg=4.5, machinability="poor", weldability="fair",
    corrosion_resistance="moderate",
    notes="AHSS. Modern safety cage material.",
    common_uses=["roll cage (competition)", "door intrusion beams", "crash structures"],
))

_add(Material(
    name="Stainless Steel 304", category="metal",
    density_kg_m3=8000, elastic_modulus_pa=193e9, shear_modulus_pa=77e9,
    poisson_ratio=0.29, yield_strength_pa=215e6, ultimate_strength_pa=505e6,
    fatigue_limit_pa=241e6, elongation_pct=40, hardness_vickers=201,
    thermal_conductivity_w_mk=16.2, specific_heat_j_kgk=500,
    thermal_expansion_per_k=17.2e-6, max_service_temp_k=1073, melting_point_k=1673,
    cost_usd_per_kg=3.5, machinability="fair", weldability="good",
    corrosion_resistance="excellent",
    notes="Austenitic stainless. Exhaust system standard.",
    common_uses=["exhaust systems", "fuel lines", "brake lines", "turbo hardware"],
))


# ── Aluminium alloys ──────────────────────────────────────────────────────────

_add(Material(
    name="Aluminium 6061-T6", category="metal",
    density_kg_m3=2700, elastic_modulus_pa=68.9e9, shear_modulus_pa=26e9,
    poisson_ratio=0.33, yield_strength_pa=276e6, ultimate_strength_pa=310e6,
    fatigue_limit_pa=96.5e6, elongation_pct=12, hardness_vickers=107,
    thermal_conductivity_w_mk=167, specific_heat_j_kgk=896,
    thermal_expansion_per_k=23.6e-6, max_service_temp_k=423, melting_point_k=925,
    cost_usd_per_kg=3.0, machinability="excellent", weldability="good",
    corrosion_resistance="good",
    notes="Most common structural aluminium. Excellent machineability.",
    common_uses=["wheels", "suspension arms", "engine block", "intercooler", "radiator"],
))

_add(Material(
    name="Aluminium 7075-T6", category="metal",
    density_kg_m3=2810, elastic_modulus_pa=71.7e9, shear_modulus_pa=26.9e9,
    poisson_ratio=0.33, yield_strength_pa=503e6, ultimate_strength_pa=572e6,
    fatigue_limit_pa=159e6, elongation_pct=11, hardness_vickers=175,
    thermal_conductivity_w_mk=130, specific_heat_j_kgk=960,
    thermal_expansion_per_k=23.4e-6, max_service_temp_k=393, melting_point_k=908,
    cost_usd_per_kg=6.0, machinability="good", weldability="fair",
    corrosion_resistance="moderate",
    notes="Aerospace grade aluminium. Highest strength Al alloy.",
    common_uses=["billet components", "uprights", "brake calipers", "aero components"],
))


# ── Carbon fibre composites ───────────────────────────────────────────────────

_add(Material(
    name="Carbon Fibre UD Prepreg (T700/Epoxy)", category="composite",
    density_kg_m3=1600, elastic_modulus_pa=135e9, shear_modulus_pa=5e9,
    poisson_ratio=0.3, yield_strength_pa=1500e6, ultimate_strength_pa=1500e6,
    fatigue_limit_pa=600e6, elongation_pct=1.5,
    thermal_conductivity_w_mk=7, specific_heat_j_kgk=800,
    thermal_expansion_per_k=0.5e-6, max_service_temp_k=393,
    cost_usd_per_kg=35, machinability="poor", weldability="n/a",
    corrosion_resistance="excellent",
    notes="Unidirectional CF prepreg. Properties vary with layup direction. Autoclave cure.",
    common_uses=["body panels", "splitters", "wings", "diffusers", "monocoque"],
))

_add(Material(
    name="Carbon Fibre Woven 2x2 Twill (T300/Epoxy)", category="composite",
    density_kg_m3=1550, elastic_modulus_pa=70e9, shear_modulus_pa=5e9,
    poisson_ratio=0.1, yield_strength_pa=600e6, ultimate_strength_pa=600e6,
    fatigue_limit_pa=300e6, elongation_pct=1.2,
    thermal_conductivity_w_mk=5, specific_heat_j_kgk=800,
    thermal_expansion_per_k=2e-6, max_service_temp_k=393,
    cost_usd_per_kg=25, machinability="poor", weldability="n/a",
    corrosion_resistance="excellent",
    notes="Woven CF. More isotropic than UD. Cosmetic and structural panels.",
    common_uses=["cosmetic panels", "interior trim", "aero body parts"],
))

_add(Material(
    name="Fibreglass (E-Glass/Epoxy)", category="composite",
    density_kg_m3=1750, elastic_modulus_pa=35e9, shear_modulus_pa=5e9,
    poisson_ratio=0.23, yield_strength_pa=280e6, ultimate_strength_pa=280e6,
    fatigue_limit_pa=120e6, elongation_pct=2.8,
    thermal_conductivity_w_mk=0.4, specific_heat_j_kgk=840,
    thermal_expansion_per_k=12e-6, max_service_temp_k=393,
    cost_usd_per_kg=6.0, machinability="fair", weldability="n/a",
    corrosion_resistance="good",
    notes="E-glass + epoxy. Good intermediate option for body kits.",
    common_uses=["structural panels", "body kits", "aero components"],
))

_add(Material(
    name="Fibreglass (E-Glass/Polyester)", category="composite",
    density_kg_m3=1800, elastic_modulus_pa=25e9, shear_modulus_pa=4e9,
    poisson_ratio=0.25, yield_strength_pa=200e6, ultimate_strength_pa=200e6,
    fatigue_limit_pa=80e6, elongation_pct=2.5,
    thermal_conductivity_w_mk=0.35, specific_heat_j_kgk=840,
    thermal_expansion_per_k=14e-6, max_service_temp_k=373,
    cost_usd_per_kg=4.0, machinability="fair", weldability="n/a",
    corrosion_resistance="good",
    notes="Budget composite. Widely used for body kits.",
    common_uses=["body kits", "bumpers", "bonnets", "wings (budget)"],
))


# ── Titanium ──────────────────────────────────────────────────────────────────

_add(Material(
    name="Titanium Grade 5 (Ti-6Al-4V)", category="metal",
    density_kg_m3=4430, elastic_modulus_pa=113.8e9, shear_modulus_pa=44e9,
    poisson_ratio=0.342, yield_strength_pa=880e6, ultimate_strength_pa=950e6,
    fatigue_limit_pa=510e6, elongation_pct=14, hardness_vickers=349,
    thermal_conductivity_w_mk=6.7, specific_heat_j_kgk=560,
    thermal_expansion_per_k=8.6e-6, max_service_temp_k=600, melting_point_k=1877,
    cost_usd_per_kg=35, machinability="poor", weldability="fair",
    corrosion_resistance="excellent",
    notes="Aerospace titanium. Exceptional strength-to-weight and corrosion resistance.",
    common_uses=["exhaust systems", "fasteners", "connecting rods (F1)", "springs"],
))

_add(Material(
    name="Magnesium AZ31B", category="metal",
    density_kg_m3=1770, elastic_modulus_pa=45e9, shear_modulus_pa=17e9,
    poisson_ratio=0.35, yield_strength_pa=200e6, ultimate_strength_pa=260e6,
    fatigue_limit_pa=90e6, elongation_pct=15,
    thermal_conductivity_w_mk=96, specific_heat_j_kgk=1020,
    thermal_expansion_per_k=26e-6, max_service_temp_k=423, melting_point_k=904,
    cost_usd_per_kg=5.0, machinability="excellent", weldability="fair",
    corrosion_resistance="poor",
    notes="Lightest structural metal. Must be protected from corrosion.",
    common_uses=["wheels (racing)", "gearbox housing", "engine covers", "seat frames"],
))


# ── Brake disc materials ──────────────────────────────────────────────────────

_add(Material(
    name="Cast Iron (Grey, Brake Grade)", category="metal",
    density_kg_m3=7150, elastic_modulus_pa=100e9, shear_modulus_pa=40e9,
    poisson_ratio=0.26, yield_strength_pa=250e6, ultimate_strength_pa=400e6,
    elongation_pct=0.5,
    thermal_conductivity_w_mk=54, specific_heat_j_kgk=460,
    thermal_expansion_per_k=10.8e-6, max_service_temp_k=873, melting_point_k=1473,
    cost_usd_per_kg=1.5, machinability="good", weldability="poor",
    corrosion_resistance="poor",
    notes="Standard brake disc material. Fades above 600°C. OEM standard.",
    common_uses=["brake discs (street)", "brake drums", "flywheel"],
))

_add(Material(
    name="Carbon-Ceramic (SiC Matrix)", category="composite",
    density_kg_m3=2000, elastic_modulus_pa=80e9, shear_modulus_pa=30e9,
    poisson_ratio=0.2, yield_strength_pa=300e6, ultimate_strength_pa=300e6,
    thermal_conductivity_w_mk=30, specific_heat_j_kgk=700,
    thermal_expansion_per_k=4e-6, max_service_temp_k=1673,
    cost_usd_per_kg=500, machinability="poor", weldability="n/a",
    corrosion_resistance="excellent",
    notes="Porsche PCCB, Ferrari CCM. ~60% lighter than cast iron. Very expensive.",
    common_uses=["Porsche PCCB", "Ferrari CCM", "high-end road/track brakes"],
))


# ── Tyre compounds ────────────────────────────────────────────────────────────

@dataclass
class TyreCompound:
    name:               str
    peak_grip_temp_c:   float
    grip_temp_window_c: float
    peak_friction_coeff:float
    cold_friction_coeff:float
    thermal_conductivity_w_mk: float
    specific_heat_j_kgk: float
    density_kg_m3:      float
    hardness_shore_a:   float
    treadwear_rating:   int
    notes:              str = ""

TYRE_COMPOUNDS: Dict[str, TyreCompound] = {
    "slick_soft": TyreCompound(
        name="Racing Slick Soft", peak_grip_temp_c=90, grip_temp_window_c=15,
        peak_friction_coeff=1.6, cold_friction_coeff=0.9,
        thermal_conductivity_w_mk=0.25, specific_heat_j_kgk=1700,
        density_kg_m3=1150, hardness_shore_a=48, treadwear_rating=0,
        notes="Qualifying compound. Extreme grip. Very narrow temp window.",
    ),
    "slick_medium": TyreCompound(
        name="Racing Slick Medium", peak_grip_temp_c=80, grip_temp_window_c=25,
        peak_friction_coeff=1.5, cold_friction_coeff=1.0,
        thermal_conductivity_w_mk=0.22, specific_heat_j_kgk=1700,
        density_kg_m3=1150, hardness_shore_a=55, treadwear_rating=0,
        notes="Race compound. Good grip over wider temp range.",
    ),
    "semi_slick": TyreCompound(
        name="Semi-Slick (200TW)", peak_grip_temp_c=65, grip_temp_window_c=30,
        peak_friction_coeff=1.35, cold_friction_coeff=1.1,
        thermal_conductivity_w_mk=0.20, specific_heat_j_kgk=1800,
        density_kg_m3=1120, hardness_shore_a=62, treadwear_rating=200,
        notes="Michelin PS Cup 2, Yokohama A052. Street legal. Good from cold.",
    ),
    "performance_street": TyreCompound(
        name="Performance Street (300TW)", peak_grip_temp_c=50, grip_temp_window_c=40,
        peak_friction_coeff=1.15, cold_friction_coeff=1.05,
        thermal_conductivity_w_mk=0.18, specific_heat_j_kgk=1900,
        density_kg_m3=1100, hardness_shore_a=68, treadwear_rating=300,
        notes="Michelin PS4S. Daily driver performance.",
    ),
    "standard_street": TyreCompound(
        name="Standard Street (500TW)", peak_grip_temp_c=40, grip_temp_window_c=50,
        peak_friction_coeff=0.95, cold_friction_coeff=0.90,
        thermal_conductivity_w_mk=0.16, specific_heat_j_kgk=2000,
        density_kg_m3=1090, hardness_shore_a=74, treadwear_rating=500,
        notes="Standard touring compound. Wide operating window.",
    ),
}


# ── Lookup functions ──────────────────────────────────────────────────────────

def get_material(name: str) -> Optional[Material]:
    return MATERIALS.get(name)

def find_materials(category: str = None, min_yield_mpa: float = None,
                   max_density: float = None, max_cost_usd_kg: float = None) -> List[Material]:
    results = list(MATERIALS.values())
    if category:
        results = [m for m in results if m.category == category]
    if min_yield_mpa:
        results = [m for m in results if m.yield_strength_pa >= min_yield_mpa * 1e6]
    if max_density:
        results = [m for m in results if m.density_kg_m3 <= max_density]
    if max_cost_usd_kg:
        results = [m for m in results if m.cost_usd_per_kg <= max_cost_usd_kg]
    return results

def best_material_for(application: str) -> List[Material]:
    application = application.lower()
    app_map = {
        "body panel":     ["Carbon Fibre Woven 2x2 Twill (T300/Epoxy)", "Fibreglass (E-Glass/Epoxy)", "Aluminium 6061-T6"],
        "wing":           ["Carbon Fibre UD Prepreg (T700/Epoxy)", "Carbon Fibre Woven 2x2 Twill (T300/Epoxy)", "Aluminium 6061-T6"],
        "splitter":       ["Carbon Fibre UD Prepreg (T700/Epoxy)", "Fibreglass (E-Glass/Epoxy)"],
        "chassis":        ["Chromoly Steel (4130)", "High Strength Steel (AISI 4340)", "Aluminium 6061-T6"],
        "roll cage":      ["Chromoly Steel (4130)", "Ultra High Strength Steel (DOCOL 1700M)"],
        "wheel":          ["Aluminium 6061-T6", "Aluminium 7075-T6", "Magnesium AZ31B"],
        "brake disc":     ["Carbon-Ceramic (SiC Matrix)", "Cast Iron (Grey, Brake Grade)"],
        "suspension arm": ["Aluminium 7075-T6", "High Strength Steel (AISI 4340)", "Chromoly Steel (4130)"],
        "exhaust":        ["Stainless Steel 304", "Titanium Grade 5 (Ti-6Al-4V)"],
        "connecting rod": ["High Strength Steel (AISI 4340)", "Titanium Grade 5 (Ti-6Al-4V)"],
    }
    for key, mat_names in app_map.items():
        if key in application:
            return [MATERIALS[n] for n in mat_names if n in MATERIALS]
    return list(MATERIALS.values())[:3]

def material_for_stress(required_yield_mpa: float, max_density: float = None,
                         max_cost: float = None, safety_factor: float = 1.5) -> List[Material]:
    actual_required = required_yield_mpa * safety_factor * 1e6
    results = [m for m in MATERIALS.values() if m.yield_strength_pa >= actual_required]
    if max_density:
        results = [m for m in results if m.density_kg_m3 <= max_density]
    if max_cost:
        results = [m for m in results if m.cost_usd_per_kg <= max_cost]
    results.sort(key=lambda m: m.specific_strength, reverse=True)
    return results

def compare_materials(names: List[str]) -> dict:
    materials = [MATERIALS[n] for n in names if n in MATERIALS]
    return {m.name: m.summary() for m in materials}


if __name__ == "__main__":
    print(f"Materials database: {len(MATERIALS)} materials")
    print(f"Tyre compounds: {len(TYRE_COMPOUNDS)}")
    print()
    print("All materials by specific strength (strength/weight):")
    sorted_mats = sorted(MATERIALS.values(), key=lambda m: m.specific_strength, reverse=True)
    for m in sorted_mats:
        print(f"  {m.name:50} σ_y={m.yield_strength_pa/1e6:6.0f}MPa  "
              f"ρ={m.density_kg_m3:5.0f}kg/m³  "
              f"σ/ρ={m.specific_strength/1e3:6.0f}kN·m/kg  "
              f"${m.cost_usd_per_kg}/kg")
    print()
    print("Best materials for a rear wing:")
    for m in best_material_for("wing"):
        print(f"  {m.name} — {m.yield_strength_pa/1e6:.0f}MPa, {m.density_kg_m3}kg/m³, ${m.cost_usd_per_kg}/kg")
