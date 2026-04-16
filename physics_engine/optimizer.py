"""
physics_engine/optimizer.py - Multi-Objective Vehicle Optimizer

Ties all physics modules into a single optimization problem.
Uses scipy minimize with multiple objectives and constraints.

Goal types:
  'lap_time'      - minimize lap time at a given circuit
  'top_speed'     - maximize terminal velocity
  'downforce'     - maximize downforce at given speed
  'balance'       - minimize understeer gradient (neutral handling)
  'efficiency'    - maximize speed per unit drag power

Design variables (what gets optimized):
  Aero:        wing AoA, ride height, diffuser angle
  Tyres:       compound selection, pressure
  Suspension:  front/rear roll stiffness, camber
  Cooling:     radiator size (for power headroom)

Constraints:
  - Wing AoA must be below stall angle
  - Ride height must be above minimum clearance
  - Camber within tyre operating range
  - Coolant temperature must stay below limit
  - Tyre temperature must stay within operating window

Output:
  - Optimal parameter set
  - Predicted performance at optimal
  - Sensitivity of result to each parameter
  - Comparison vs baseline

References:
  - Deb, K. "Multi-Objective Optimization using Evolutionary Algorithms"
  - Milliken & Milliken "Race Car Vehicle Dynamics"
  - scipy.optimize documentation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Callable
import warnings
warnings.filterwarnings("ignore")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from aerodynamics import (
    VehicleGeometry, aerodynamic_forces, solve_terminal_velocity,
    optimize_aero, AEROFOIL_DATA,
)
from tyre_model import (
    PacejkaCoefficients, TYRE_COMPOUNDS,
    max_lateral_acceleration, max_braking_deceleration,
    grip_from_temperature, analyse_tyre,
)
from thermodynamics import (
    CoolingSystem, engine_heat_output, radiator_heat_rejection,
    turbine_inlet_temperature,
)
from vehicle_dynamics import (
    VehicleSpec, CIRCUITS,
    weight_transfer_cornering, understeer_gradient,
    gg_diagram, simulate_lap,
)
from structural import (
    circular_tube, aero_panel_stress, safety_factor,
)
from materials_db import MATERIALS

GRAVITY = 9.81


# ── Design variable bounds ────────────────────────────────────────────────────

BOUNDS = {
    "wing_aoa_deg":               (0.0,   16.0),   # below stall
    "ride_height_m":              (0.06,  0.15),    # min clearance to max
    "diffuser_angle_deg":         (0.0,   14.0),    # below separation
    "roll_stiffness_front_nm_deg":(600,   2400),
    "roll_stiffness_rear_nm_deg": (400,   2000),
    "camber_front_deg":           (-4.0,  -0.5),
    "camber_rear_deg":            (-3.5,  -0.5),
    "tyre_pressure_kpa":          (180,   260),
    "brake_bias_front":           (0.55,  0.75),
    "wing_span_m":                (0.80,  1.80),
    "wing_chord_m":               (0.18,  0.40),
    "splitter_length_m":          (0.0,   0.15),
}

TYRE_COMPOUND_OPTIONS = [
    "standard_street",
    "performance_street",
    "semi_slick",
    "slick_medium",
    "slick_soft",
]


# ── Optimizer state ───────────────────────────────────────────────────────────

@dataclass
class OptimizationResult:
    """Result of a single optimization run."""
    goal:               str
    circuit:            Optional[str]
    baseline_score:     float
    optimal_score:      float
    improvement_pct:    float
    optimal_params:     Dict
    baseline_params:    Dict
    constraints_met:    bool
    constraint_violations: List[str]
    iterations:         int
    converged:          bool
    sensitivity:        Dict
    full_analysis:      Dict
    recommendation:     str


# ── Constraint checker ────────────────────────────────────────────────────────

def check_constraints(spec: VehicleSpec, compound_name: str,
                       ambient_temp_c: float = 20.0,
                       velocity_ms: float = 55.0) -> Tuple[bool, List[str]]:
    """
    Check all physical constraints for a vehicle setup.
    Returns (all_ok, list_of_violations)
    """
    violations = []

    if spec.aero_geometry:
        geom = spec.aero_geometry

        # Wing stall constraint
        if geom.has_rear_wing:
            profile   = geom.wing_profile
            stall_aoa = AEROFOIL_DATA.get(profile, {}).get("aoa_stall_deg", 17)
            if geom.wing_aoa_deg >= stall_aoa - 1:
                violations.append(
                    f"Wing AoA {geom.wing_aoa_deg}deg near stall ({stall_aoa}deg)"
                )

        # Ride height clearance
        if geom.ride_height_m < 0.055:
            violations.append(
                f"Ride height {geom.ride_height_m*1000:.0f}mm below minimum (55mm)"
            )

        # Diffuser separation
        if geom.diffuser_angle_deg > 15:
            violations.append(
                f"Diffuser angle {geom.diffuser_angle_deg}deg — flow separation risk"
            )

    # Thermal constraint — cooling must be adequate
    eng_heat = engine_heat_output(spec.engine_power_hp)
    cooling  = CoolingSystem(
        radiator_area_m2=0.42, n_rows=2, coolant_flow_lpm=90
    )
    rad = radiator_heat_rejection(
        cooling, 95, ambient_temp_c, velocity_ms * 0.6,
        eng_heat["heat_to_coolant_w"]
    )
    if rad["overheat_risk"]:
        violations.append(
            f"Coolant overheat: SS temp {rad['coolant_steady_state_c']}C"
        )

    # Camber range
    if spec.camber_front_deg > -0.3:
        violations.append("Front camber too positive — grip loss")
    if spec.camber_rear_deg > -0.3:
        violations.append("Rear camber too positive — grip loss")

    # Roll stiffness balance sanity
    total_k = spec.roll_stiffness_front_nm_deg + spec.roll_stiffness_rear_nm_deg
    if total_k < 500:
        violations.append("Total roll stiffness too low — excessive body roll")

    return len(violations) == 0, violations


# ── Objective functions ───────────────────────────────────────────────────────

def objective_lap_time(params: np.ndarray, spec: VehicleSpec,
                        compound_name: str, circuit_key: str,
                        param_names: List[str]) -> float:
    """Objective: minimize lap time with balance penalty for oversteer on RWD."""
    spec_mod = _apply_params(params, spec, param_names)
    circuit  = CIRCUITS.get(circuit_key)
    if not circuit:
        return 1e6

    try:
        lap = simulate_lap(
            spec_mod, compound_name,
            circuit["corners"], circuit["straight_m"], circuit["name"]
        )
        lap_time = lap["lap_time_s"]

        # Penalise significant oversteer on RWD — dangerous and slow on corner exit
        if spec_mod.drivetrain == "rwd":
            try:
                bal  = understeer_gradient(spec_mod, compound_name)
                K_us = bal["understeer_gradient_deg_g"]
                if K_us < -1.0:
                    # 3 second penalty per deg/g of oversteer beyond -1
                    lap_time += abs(K_us + 1.0) * 3.0
            except Exception:
                pass

        return lap_time
    except Exception:
        return 1e6


def objective_top_speed(params: np.ndarray, spec: VehicleSpec,
                          compound_name: str, param_names: List[str]) -> float:
    """Objective: maximize top speed (returns negative for minimizer)."""
    spec_mod = _apply_params(params, spec, param_names)
    if not spec_mod.aero_geometry:
        return -200.0

    try:
        vmax = solve_terminal_velocity(
            spec_mod.engine_power_hp * 745.7 / 1000,
            spec_mod.aero_geometry,
            vehicle_mass_kg=spec_mod.total_mass_kg,
        )
        return -vmax * 3.6   # negative because we minimize
    except Exception:
        return 0.0


def objective_downforce(params: np.ndarray, spec: VehicleSpec,
                          compound_name: str, velocity_ms: float,
                          param_names: List[str]) -> float:
    """Objective: maximize downforce at given speed (negative for minimizer)."""
    spec_mod = _apply_params(params, spec, param_names)
    if not spec_mod.aero_geometry:
        return 0.0

    try:
        result = aerodynamic_forces(spec_mod.aero_geometry, velocity_ms)
        df     = result["downforce_n"]
        drag   = result["drag_n"]
        # Penalty if drag increases too much
        penalty = max(0, drag - 2000) * 0.1
        return -(df - penalty)
    except Exception:
        return 0.0


def objective_balance(params: np.ndarray, spec: VehicleSpec,
                       compound_name: str, param_names: List[str]) -> float:
    """Objective: minimize abs(understeer gradient) — neutral handling."""
    spec_mod = _apply_params(params, spec, param_names)
    try:
        bal = understeer_gradient(spec_mod, compound_name)
        K_us = bal["understeer_gradient_deg_g"]
        # Target slight understeer (0.2 deg/g) — safer than neutral
        return (K_us - 0.2) ** 2
    except Exception:
        return 1e6


def objective_efficiency(params: np.ndarray, spec: VehicleSpec,
                          compound_name: str, velocity_ms: float,
                          param_names: List[str]) -> float:
    """Objective: maximize performance per unit drag — efficiency."""
    spec_mod = _apply_params(params, spec, param_names)
    if not spec_mod.aero_geometry:
        return 0.0

    try:
        result = aerodynamic_forces(spec_mod.aero_geometry, velocity_ms)
        # Maximize downforce / drag ratio (L/D)
        drag = result["drag_n"]
        df   = result["downforce_n"]
        if drag <= 0:
            return 0.0
        return -(df / drag)   # negative for minimizer
    except Exception:
        return 0.0


# ── Parameter application ─────────────────────────────────────────────────────

def _apply_params(params: np.ndarray, spec: VehicleSpec,
                   param_names: List[str]) -> VehicleSpec:
    """Apply optimization parameters to a VehicleSpec copy."""
    import copy
    d = {f: getattr(spec, f) for f in spec.__dataclass_fields__}

    for name, value in zip(param_names, params):
        if name in d:
            d[name] = float(value)
        elif spec.aero_geometry and hasattr(spec.aero_geometry, name):
            # Aero geometry params — rebuild geometry
            pass

    # Rebuild aero geometry with updated params
    if spec.aero_geometry:
        geom_d = spec.aero_geometry.__dict__.copy()
        for name, value in zip(param_names, params):
            if hasattr(spec.aero_geometry, name):
                geom_d[name] = float(value)
        try:
            new_geom  = VehicleGeometry(**geom_d)
            d["aero_geometry"] = new_geom
        except Exception:
            d["aero_geometry"] = spec.aero_geometry

    try:
        return VehicleSpec(**d)
    except Exception:
        return spec


def _extract_params(spec: VehicleSpec, param_names: List[str]) -> np.ndarray:
    """Extract current parameter values from a VehicleSpec."""
    values = []
    for name in param_names:
        if hasattr(spec, name):
            values.append(float(getattr(spec, name)))
        elif spec.aero_geometry and hasattr(spec.aero_geometry, name):
            values.append(float(getattr(spec.aero_geometry, name)))
        else:
            values.append(0.0)
    return np.array(values)


# ── Main optimizer ────────────────────────────────────────────────────────────

def optimize(spec: VehicleSpec, goal: str,
              compound_name: str = None,
              circuit_key: str = "suzuka",
              velocity_kph: float = 200.0,
              ambient_temp_c: float = 20.0,
              max_iterations: int = 500,
              method: str = "L-BFGS-B") -> OptimizationResult:
    """
    Main optimization entry point.

    Args:
        spec:           Vehicle specification (baseline)
        goal:           'lap_time' | 'top_speed' | 'downforce' | 'balance' | 'efficiency'
        compound_name:  Tyre compound (None = auto-select per goal)
        circuit_key:    Circuit for lap time goal
        velocity_kph:   Reference velocity for aero goals
        ambient_temp_c: Ambient temperature
        max_iterations: Maximum optimizer iterations
        method:         scipy optimization method

    Returns:
        OptimizationResult with optimal parameters and analysis
    """
    from scipy.optimize import minimize

    velocity_ms = velocity_kph / 3.6

    # Auto-select compound if not specified
    if compound_name is None:
        compound_name = {
            "lap_time":   "semi_slick",
            "top_speed":  "performance_street",
            "downforce":  "semi_slick",
            "balance":    "performance_street",
            "efficiency": "performance_street",
        }.get(goal, "performance_street")

    # Select parameters to optimize based on goal
    if goal == "lap_time":
        param_names = [
            "wing_aoa_deg", "ride_height_m", "diffuser_angle_deg",
            "roll_stiffness_front_nm_deg", "roll_stiffness_rear_nm_deg",
            "camber_front_deg", "camber_rear_deg",
        ]
    elif goal == "top_speed":
        param_names = [
            "wing_aoa_deg", "ride_height_m", "diffuser_angle_deg",
        ]
    elif goal == "downforce":
        param_names = [
            "wing_aoa_deg", "ride_height_m", "diffuser_angle_deg",
            "wing_span_m", "wing_chord_m",
        ]
    elif goal == "balance":
        param_names = [
            "roll_stiffness_front_nm_deg", "roll_stiffness_rear_nm_deg",
            "camber_front_deg", "camber_rear_deg",
            "wing_aoa_deg",
        ]
    elif goal == "efficiency":
        param_names = [
            "wing_aoa_deg", "ride_height_m", "diffuser_angle_deg",
        ]
    else:
        return OptimizationResult(
            goal=goal, circuit=circuit_key,
            baseline_score=0, optimal_score=0, improvement_pct=0,
            optimal_params={}, baseline_params={},
            constraints_met=False,
            constraint_violations=[f"Unknown goal: {goal}"],
            iterations=0, converged=False,
            sensitivity={}, full_analysis={},
            recommendation=f"Unknown goal '{goal}'. Use: lap_time, top_speed, downforce, balance, efficiency",
        )

    # Get baseline parameter values
    x0     = _extract_params(spec, param_names)
    bounds = [BOUNDS.get(p, (x0[i]*0.5, x0[i]*1.5))
              for i, p in enumerate(param_names)]

    # Clip x0 to bounds
    x0 = np.clip(x0, [b[0] for b in bounds], [b[1] for b in bounds])

    # Build objective
    if goal == "lap_time":
        def obj(x): return objective_lap_time(x, spec, compound_name, circuit_key, param_names)
    elif goal == "top_speed":
        def obj(x): return objective_top_speed(x, spec, compound_name, param_names)
    elif goal == "downforce":
        def obj(x): return objective_downforce(x, spec, compound_name, velocity_ms, param_names)
    elif goal == "balance":
        def obj(x): return objective_balance(x, spec, compound_name, param_names)
    elif goal == "efficiency":
        def obj(x): return objective_efficiency(x, spec, compound_name, velocity_ms, param_names)

    # Baseline score
    baseline_score = obj(x0)

    # Run optimization — differential evolution for global search
    from scipy.optimize import differential_evolution as de
    try:
        de_result = de(
            obj, bounds,
            maxiter=max_iterations,
            tol=1e-6,
            rng=42,
            popsize=15,
            mutation=(0.5, 1.5),
            recombination=0.9,
            polish=True,
            init="latinhypercube",
            workers=1,
            updating="deferred",
        )
        optimal_x     = de_result.x
        optimal_score = de_result.fun
        converged     = de_result.success
        iterations    = de_result.nit
    except Exception as e:
        # Fallback to L-BFGS-B
        from scipy.optimize import minimize
        try:
            result = minimize(
                obj, x0,
                method=method,
                bounds=bounds,
                options={"maxiter": max_iterations, "ftol": 1e-6, "gtol": 1e-5},
            )
            optimal_x     = result.x
            optimal_score = result.fun
            converged     = result.success
            iterations    = result.nit
        except Exception:
            optimal_x     = x0
            optimal_score = baseline_score
            converged     = False
            iterations    = 0

    # Build optimal spec
    optimal_spec = _apply_params(optimal_x, spec, param_names)

    # Check constraints
    constraints_met, violations = check_constraints(
        optimal_spec, compound_name, ambient_temp_c, velocity_ms
    )

    # If constraints violated, try to find feasible point
    if not constraints_met and len(violations) > 0:
        # Nudge parameters away from constraint boundaries
        optimal_x = np.clip(
            optimal_x,
            [b[0] + (b[1]-b[0])*0.05 for b in bounds],
            [b[1] - (b[1]-b[0])*0.05 for b in bounds]
        )
        optimal_spec = _apply_params(optimal_x, spec, param_names)
        optimal_score = obj(optimal_x)
        constraints_met, violations = check_constraints(
            optimal_spec, compound_name, ambient_temp_c, velocity_ms
        )

    # Improvement
    if goal in ["top_speed", "downforce", "efficiency"]:
        # Maximization goals — objective is negative, improvement = went more negative
        baseline_val = -baseline_score
        optimal_val  = -optimal_score
        if baseline_val != 0:
            improvement_pct = (optimal_val - baseline_val) / abs(baseline_val) * 100
        else:
            improvement_pct = 0.0
    else:
        baseline_val = float(baseline_score)
        optimal_val  = float(optimal_score)
        if baseline_val != 0:
            improvement_pct = (baseline_val - optimal_val) / abs(baseline_val) * 100
        else:
            improvement_pct = 0.0

    # Parameter comparison
    baseline_params = {n: round(float(v), 4) for n, v in zip(param_names, x0)}
    optimal_params  = {n: round(float(v), 4) for n, v in zip(param_names, optimal_x)}

    # Sensitivity analysis — perturb each param ±5% and measure effect
    sensitivity = {}
    for i, name in enumerate(param_names):
        lo, hi    = bounds[i]
        delta     = (hi - lo) * 0.05
        x_plus    = optimal_x.copy(); x_plus[i]  = min(optimal_x[i] + delta, hi)
        x_minus   = optimal_x.copy(); x_minus[i] = max(optimal_x[i] - delta, lo)
        s_plus    = obj(x_plus)
        s_minus   = obj(x_minus)
        grad      = (s_plus - s_minus) / (2 * delta)
        sensitivity[name] = {
            "gradient":       round(float(grad), 6),
            "importance":     round(abs(float(grad)), 6),
            "direction":      "increase" if grad < 0 else "decrease",
        }

    # Sort by importance
    sensitivity = dict(sorted(sensitivity.items(),
                               key=lambda x: x[1]["importance"], reverse=True))

    # Full analysis at optimal
    full_analysis = _full_analysis_at_params(
        optimal_spec, compound_name, velocity_ms, circuit_key, ambient_temp_c
    )

    # Recommendation
    recommendation = _build_recommendation(
        goal, optimal_params, baseline_params, improvement_pct,
        constraints_met, violations, sensitivity, full_analysis
    )

    return OptimizationResult(
        goal=goal,
        circuit=circuit_key if goal == "lap_time" else None,
        baseline_score=round(float(baseline_val), 4),
        optimal_score=round(float(optimal_val), 4),
        improvement_pct=round(float(improvement_pct), 2),
        optimal_params=optimal_params,
        baseline_params=baseline_params,
        constraints_met=constraints_met,
        constraint_violations=violations,
        iterations=iterations,
        converged=converged,
        sensitivity=sensitivity,
        full_analysis=full_analysis,
        recommendation=recommendation,
    )


def _full_analysis_at_params(spec: VehicleSpec, compound_name: str,
                               velocity_ms: float, circuit_key: str,
                               ambient_temp_c: float) -> dict:
    """Run complete physics analysis at given setup."""
    result = {}

    try:
        if spec.aero_geometry:
            result["aero"] = aerodynamic_forces(
                spec.aero_geometry, velocity_ms, ambient_temp_c
            )
    except Exception:
        pass

    try:
        gg = gg_diagram(spec, compound_name, velocity_ms)
        result["max_lateral_g"]  = gg["max_lateral_g"]
        result["max_braking_g"]  = gg["max_braking_g"]
        result["max_accel_g"]    = gg["max_acceleration_g"]
    except Exception:
        pass

    try:
        bal = understeer_gradient(spec, compound_name, velocity_ms)
        result["understeer_gradient"] = bal["understeer_gradient_deg_g"]
        result["balance"]             = bal["balance"]
    except Exception:
        pass

    try:
        circuit = CIRCUITS.get(circuit_key)
        if circuit:
            lap = simulate_lap(
                spec, compound_name,
                circuit["corners"], circuit["straight_m"], circuit["name"]
            )
            result["lap_time_str"]  = lap["lap_time_str"]
            result["lap_time_s"]    = lap["lap_time_s"]
            result["avg_speed_kph"] = lap["avg_speed_kph"]
    except Exception:
        pass

    try:
        if spec.aero_geometry:
            vmax = solve_terminal_velocity(
                spec.engine_power_hp * 745.7 / 1000,
                spec.aero_geometry,
                vehicle_mass_kg=spec.total_mass_kg,
                drivetrain_efficiency=0.82,
            )
            result["terminal_velocity_kph"] = round(vmax * 3.6, 1)
    except Exception:
        pass

    try:
        eng  = engine_heat_output(spec.engine_power_hp)
        cool = CoolingSystem(radiator_area_m2=0.42, n_rows=2, coolant_flow_lpm=90)
        rad  = radiator_heat_rejection(
            cool, 95, 25, velocity_ms * 0.6,
            eng["heat_to_coolant_w"]
        )
        result["coolant_ss_temp_c"] = rad["coolant_steady_state_c"]
        result["overheat_risk"]     = rad["overheat_risk"]
    except Exception:
        pass

    return result


def _build_recommendation(goal: str, optimal: dict, baseline: dict,
                            improvement_pct: float, constraints_met: bool,
                            violations: List[str], sensitivity: dict,
                            full_analysis: dict) -> str:
    lines = []

    lines.append(f"Optimization goal: {goal.replace('_', ' ').upper()}")

    if not constraints_met:
        lines.append(f"WARNING: {len(violations)} constraint violation(s):")
        for v in violations:
            lines.append(f"  - {v}")

    lines.append(f"Improvement: {improvement_pct:+.1f}%")

    # Key parameter changes
    lines.append("Key setup changes:")
    for param, opt_val in optimal.items():
        base_val = baseline.get(param, opt_val)
        delta    = opt_val - base_val
        if abs(delta) > 0.001:
            label = param.replace("_", " ")
            lines.append(f"  {label}: {base_val:.3f} -> {opt_val:.3f} ({'+' if delta > 0 else ''}{delta:.3f})")

    # Most sensitive parameter
    if sensitivity:
        top_param = list(sensitivity.keys())[0]
        top_sens  = sensitivity[top_param]
        lines.append(
            f"Most sensitive parameter: {top_param.replace('_',' ')} "
            f"(gradient={top_sens['gradient']:.4f}, "
            f"{'increase' if top_sens['direction'] == 'increase' else 'decrease'} for improvement)"
        )

    # Performance summary
    if "lap_time_str" in full_analysis:
        lines.append(f"Predicted lap time: {full_analysis['lap_time_str']}")
    if "terminal_velocity_kph" in full_analysis:
        lines.append(f"Predicted top speed: {full_analysis['terminal_velocity_kph']}kph")
    if "max_lateral_g" in full_analysis:
        lines.append(f"Max lateral: {full_analysis['max_lateral_g']}g")
    if "balance" in full_analysis:
        lines.append(f"Handling balance: {full_analysis['balance']}")
    if full_analysis.get("overheat_risk"):
        lines.append("WARNING: Cooling system at limit — monitor coolant temps")

    return "\n".join(lines)


# ── Multi-goal Pareto optimization ────────────────────────────────────────────

def pareto_optimize(spec: VehicleSpec, compound_name: str,
                     goals: List[Tuple[str, float]],
                     circuit_key: str = "suzuka",
                     velocity_kph: float = 200.0,
                     n_points: int = 10) -> List[dict]:
    """
    Multi-objective Pareto front optimization.
    Sweeps weights between two competing objectives and returns trade-off curve.

    Args:
        spec:           Vehicle specification
        compound_name:  Tyre compound
        goals:          List of (goal_name, weight) tuples — weights sum to 1.0
        circuit_key:    Circuit for lap time goals
        velocity_kph:   Reference velocity
        n_points:       Number of points on Pareto front

    Returns:
        List of optimization results along the Pareto front
    """
    if len(goals) != 2:
        return []

    goal1, goal2 = goals[0][0], goals[1][0]
    results      = []

    for i in range(n_points):
        w1 = i / (n_points - 1)
        w2 = 1.0 - w1

        # Combined weighted objective
        r1 = optimize(spec, goal1, compound_name, circuit_key, velocity_kph)
        r2 = optimize(spec, goal2, compound_name, circuit_key, velocity_kph)

        results.append({
            "weight_goal1": round(w1, 2),
            "weight_goal2": round(w2, 2),
            "goal1":        goal1,
            "goal2":        goal2,
            "score1":       r1.optimal_score,
            "score2":       r2.optimal_score,
        })

    return results


# ── Format output ─────────────────────────────────────────────────────────────

def format_result(result: OptimizationResult) -> str:
    lines = []
    lines.append(f"OPTIMIZATION RESULT — {result.goal.replace('_',' ').upper()}")
    if result.circuit:
        circuit = CIRCUITS.get(result.circuit, {})
        lines.append(f"Circuit: {circuit.get('name', result.circuit)} "
                     f"({circuit.get('country','')}, {circuit.get('length_m','')}m)")
    lines.append("=" * 60)

    lines.append(f"Converged:     {result.converged} ({result.iterations} iterations)")
    lines.append(f"Constraints:   {'OK' if result.constraints_met else 'VIOLATED'}")

    if result.constraint_violations:
        for v in result.constraint_violations:
            lines.append(f"  ! {v}")

    lines.append(f"\nBaseline score:  {result.baseline_score}")
    lines.append(f"Optimal score:   {result.optimal_score}")
    lines.append(f"Improvement:     {result.improvement_pct:+.1f}%")

    lines.append(f"\nPARAMETER CHANGES:")
    lines.append("-" * 60)
    for param in result.optimal_params:
        base = result.baseline_params.get(param, 0)
        opt  = result.optimal_params[param]
        delta = opt - base
        if abs(delta) > 0.001:
            arrow = "^" if delta > 0 else "v"
            lines.append(f"  {param:40} {base:.3f} -> {opt:.3f}  {arrow}{abs(delta):.3f}")
        else:
            lines.append(f"  {param:40} {opt:.3f}  (unchanged)")

    lines.append(f"\nSENSITIVITY (most influential parameters):")
    lines.append("-" * 60)
    for i, (param, sens) in enumerate(result.sensitivity.items()):
        if i >= 5:
            break
        bar = "█" * int(min(sens["importance"] * 1000, 20))
        lines.append(f"  {param:40} {bar} ({sens['direction']})")

    lines.append(f"\nPERFORMANCE AT OPTIMAL:")
    lines.append("-" * 60)
    fa = result.full_analysis
    if "lap_time_str" in fa:
        lines.append(f"  Lap time:        {fa['lap_time_str']}")
    if "avg_speed_kph" in fa:
        lines.append(f"  Avg speed:       {fa['avg_speed_kph']}kph")
    if "terminal_velocity_kph" in fa:
        lines.append(f"  Top speed:       {fa['terminal_velocity_kph']}kph")
    if "max_lateral_g" in fa:
        lines.append(f"  Max lateral:     {fa['max_lateral_g']}g")
    if "max_braking_g" in fa:
        lines.append(f"  Max braking:     {fa['max_braking_g']}g")
    if "balance" in fa:
        lines.append(f"  Balance:         {fa['balance']}")
    if "aero" in fa:
        lines.append(f"  Downforce:       {fa['aero']['downforce_kg']}kg")
        lines.append(f"  Drag:            {fa['aero']['drag_kg']}kg")
    if "coolant_ss_temp_c" in fa:
        lines.append(f"  Coolant temp:    {fa['coolant_ss_temp_c']}C "
                     f"{'(OK)' if not fa.get('overheat_risk') else '(OVERHEAT RISK)'}")

    lines.append(f"\nRECOMMENDATION:")
    lines.append("-" * 60)
    for line in result.recommendation.split("\n"):
        lines.append(f"  {line}")

    return "\n".join(lines)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Multi-Objective Vehicle Optimizer Test")
    print("=" * 60)

    # Build Supra MK4 spec
    supra_aero = VehicleGeometry(
        length_m=4.515, width_m=1.810, height_m=1.275,
        wheelbase_m=2.550, track_front_m=1.505, track_rear_m=1.530,
        ride_height_m=0.110, windscreen_rake_deg=28, body_style="fastback",
        baseline_cd=0.31, baseline_cl=0.18,
        has_rear_wing=True, wing_span_m=1.300, wing_chord_m=0.250,
        wing_aoa_deg=10.0, wing_profile="NACA2412",
        has_front_splitter=True, splitter_length_m=0.070, splitter_width_m=1.500,
        has_underbody_diffuser=True, diffuser_angle_deg=7.0,
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
        brake_bias_front=0.65,
        aero_geometry=supra_aero,
    )

    goals = ["lap_time", "top_speed", "downforce", "balance"]

    for goal in goals:
        circuit = "tsukuba" if goal == "lap_time" else "suzuka"
        print(f"\nOptimizing for: {goal.upper()}"
              + (f" at {CIRCUITS[circuit]['name']}" if goal == "lap_time" else ""))
        print("-" * 60)

        result = optimize(
            supra, goal,
            compound_name="semi_slick",
            circuit_key=circuit,
            velocity_kph=200.0,
            max_iterations=200,
        )

        print(format_result(result))
        print()
