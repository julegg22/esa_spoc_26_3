"""Heavy differential evolution on ONE inclined GEO pair (267, 185).

Tests whether 30-60min of SOA heavy optimization can find feasibility.
If yes → optimization path works. If no → physics seeding required.

Strategy:
- Seed population around Lambert solutions (best ones we know)
- 8-worker parallel DE
- 50 popsize, 200 generations
- Penalty-augmented objective
"""
import sys
import time
import numpy as np
from scipy.optimize import differential_evolution
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0

UDP_PATH = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def objective(p, idE=267, idL=185):
    """11-var objective: -mass for feasible, penalty for infeasible (smooth penalty)."""
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    raan_e, argp_e, ea_dep = p[0], p[1], p[2]
    dv0 = p[3:6]
    dv1 = p[6:9]
    T1, T2 = max(p[9], 0.01), max(p[10], 0.0)

    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return 1e6
    # distance from Moon center
    mu = 0.01215058439470971
    moon_ctr = np.array([1.0 - mu, 0.0, 0.0])
    r_synodic = np.array(pv_arr[0])
    r_from_moon = np.linalg.norm(r_synodic - moon_ctr) * L
    r_err = abs(r_from_moon - aL)
    # Always-defined penalty: r_err encourages approach to feasibility
    penalty = 1e4 + r_err / 100.0  # for infeasible: scale to ~ km-level

    dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return penalty
    dv2, _ = dv2_res
    dv_total_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
                    + np.linalg.norm(dv2)) * V
    mass = max(0.0, 5000 * np.exp(-dv_total_ms / (311 * 9.80665)) - 500)
    return -mass


_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(UDP_PATH)


def main():
    _init()
    udp = _UDP[0]
    idE, idL = 267, 185
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    print(f"Pair ({idE},{idL}): aE={aE/1e3:.0f}km iE={iE:.2f}, aL={aL/1e3:.0f}km iL={iL:.2f}",
          flush=True)
    print(f"Theoretical Hohmann + plane change ~2200 m/s → ~1700 kg expected\n", flush=True)

    # 11-D bounds
    pi2 = 2 * np.pi
    bounds = [
        (0, pi2),       # raan_e
        (0, pi2),       # argp_e
        (0, pi2),       # ea_dep
        (-3.0, 3.0),    # dv0_x  (nondim, 1 unit ≈ 1.023 km/s)
        (-3.0, 3.0),    # dv0_y
        (-3.0, 3.0),    # dv0_z
        (-1.0, 1.0),    # dv1_x  (smaller, mid-course)
        (-1.0, 1.0),    # dv1_y
        (-1.0, 1.0),    # dv1_z
        (0.5, 4.0),     # T1 (1 unit ≈ 4.3 days)
        (0.0, 2.0),     # T2
    ]

    print("Starting scipy differential_evolution (popsize=15, maxiter=150, workers=8)...",
          flush=True)
    print("Expected wall: 20-30 min.", flush=True)

    best_history = []

    def callback(x, convergence):
        f = objective(x)
        ts = time.time() - t_start
        best_history.append((ts, f))
        if len(best_history) % 5 == 0:
            print(f"  [t={ts:.0f}s] best_obj={f:.2f} convergence={convergence:.4f}",
                  flush=True)
        if f < 0:
            print(f"  *** FEASIBLE found: f={f:.2f} (mass={-f:.0f}kg) at t={ts:.0f}s ***",
                  flush=True)
        return False

    t_start = time.time()
    try:
        result = differential_evolution(
            objective, bounds,
            strategy='best1bin', popsize=15, maxiter=150,
            mutation=(0.5, 1.5), recombination=0.7,
            workers=1,  # workers>1 requires pickle; objective uses global state
            seed=42, callback=callback, polish=False, disp=False, tol=1e-3,
        )
    except Exception as e:
        print(f"DE FAILED: {e}", flush=True)
        return

    wall = time.time() - t_start
    print(f"\nDE done in {wall:.0f}s, final obj={result.fun:.2f}", flush=True)
    if result.fun < 0:
        print(f"*** SUCCESS: mass={-result.fun:.0f} kg ***", flush=True)
    else:
        print(f"FAILED: no feasibility (best penalty {result.fun:.2f})", flush=True)


if __name__ == "__main__":
    main()
