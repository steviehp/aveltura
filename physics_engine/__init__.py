"""
physics_engine — Aveltura Vehicle Physics Engine

Modules:
  materials_db      — Material properties database
  aerodynamics      — Aerodynamic force calculation and virtual wind tunnel
  tyre_model        — Pacejka Magic Formula grip and thermal model
  thermodynamics    — Brake, engine, turbo, intercooler thermal analysis
  structural        — Stress, fatigue, buckling, material selection
  vehicle_dynamics  — Weight transfer, suspension, lap simulation
  optimizer         — Multi-objective vehicle optimizer
"""

from .materials_db    import MATERIALS, TYRE_COMPOUNDS, get_material, best_material_for, material_for_stress
from .aerodynamics    import VehicleGeometry, aerodynamic_forces, wing_forces, solve_terminal_velocity, virtual_wind_tunnel, optimize_aero
from .tyre_model      import TyreGeometry, PacejkaCoefficients, TYRE_COMPOUNDS, analyse_tyre, max_lateral_acceleration, max_braking_deceleration
from .thermodynamics  import BrakeDisc, CoolingSystem, engine_heat_output, full_thermal_analysis
from .structural      import circular_tube, aero_panel_stress, analyse_roll_cage_tube, optimize_material, sn_curve_life
from .vehicle_dynamics import VehicleSpec, CIRCUITS, full_vehicle_analysis, simulate_lap, understeer_gradient
from .optimizer       import optimize, format_result, OptimizationResult

__version__ = "1.0.0"
__all__ = [
    "MATERIALS", "TYRE_COMPOUNDS", "get_material", "best_material_for", "material_for_stress",
    "VehicleGeometry", "aerodynamic_forces", "wing_forces", "solve_terminal_velocity",
    "virtual_wind_tunnel", "optimize_aero",
    "TyreGeometry", "PacejkaCoefficients", "analyse_tyre",
    "max_lateral_acceleration", "max_braking_deceleration",
    "BrakeDisc", "CoolingSystem", "engine_heat_output", "full_thermal_analysis",
    "circular_tube", "aero_panel_stress", "analyse_roll_cage_tube",
    "optimize_material", "sn_curve_life",
    "VehicleSpec", "CIRCUITS", "full_vehicle_analysis", "simulate_lap",
    "understeer_gradient",
    "optimize", "format_result", "OptimizationResult",
]
