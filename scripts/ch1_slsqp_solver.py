"""Heavy-optimization Ch1 trajectory solver: 11-var multi-start SLSQP/NM.

Strategy:
- pv0 guaranteed on Earth orbit via earth_orbit_state (3 free angles)
- 6 burn components + 2 TOFs = 11 free vars total
- arrival_radius_error <= 384m is the feasibility constraint
- Objective: minimize total dv
- Multi-start with many random ICs to find globally-best feasible solution
"""
import sys
import time
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv


def evaluate(p, udp, idE, idL, aE, eE, iE, aL, eL, iL):
    """Evaluate 11-var point. Returns (mass, row, total_dv_ms, r_err_m) or None."""
    raan_e, argp_e, ea_dep = p[0], p[1], p[2]
    dv0 = p[3:6]
    dv1 = p[6:9]
    T1, T2 = max(p[9], 0.01), max(p[10], 0.0)

    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return None

    # Distance from Moon
    pv_arr_arr = np.array(pv_arr[0])
    moon_ctr = np.array([1.0 - 0.01215058439470971, 0.0, 0.0])
    r_from_moon = np.linalg.norm(pv_arr_arr - moon_ctr) * L
    r_err_m = abs(r_from_moon - aL)

    dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return ("infeasible", r_err_m)
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
            *dv0.tolist(), *dv1.tolist(), *dv2.tolist(), T1, T2]
    f = udp.fitness(row)[0]
    if f >= 0:
        return ("infeasible", r_err_m)
    mass = -f
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
              + np.linalg.norm(dv2)) * V
    return (mass, row, dv_ms, r_err_m)


def neg_mass_objective(p, udp, idE, idL, aE, eE, iE, aL, eL, iL):
    """Penalty-based objective: -mass for feasible, large penalty for infeasible."""
    res = evaluate(p, udp, idE, idL, aE, eE, iE, aL, eL, iL)
    if res is None or res[0] == "infeasible":
        r_err = res[1] if (res and len(res) > 1) else 1e9
        # Penalty proportional to constraint violation
        return 1e3 + r_err / L * 1e3  # encourage approach to feasibility
    return -res[0]


def solve_pair_slsqp(udp, idE, idL, n_starts=30, max_iter=150, seed=0):
    """Multi-start Nelder-Mead on 11-var problem."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    rng = np.random.default_rng(seed)
    best = None
    t_start = time.time()

    def neg_obj(p):
        return neg_mass_objective(p, udp, idE, idL, aE, eE, iE, aL, eL, iL)

    for k in range(n_starts):
        # Random initial point spanning the relevant parameter space
        x0 = np.array([
            rng.uniform(0, 2 * np.pi),       # raan_e
            rng.uniform(0, 2 * np.pi),       # argp_e
            rng.uniform(0, 2 * np.pi),       # ea_dep
            rng.uniform(-3, 3),              # dv0_x  (nondim, max ~3 ≈ 3 km/s)
            rng.uniform(-3, 3),              # dv0_y
            rng.uniform(-3, 3),              # dv0_z
            rng.uniform(-0.5, 0.5),          # dv1_x  (smaller, mid-course)
            rng.uniform(-0.5, 0.5),          # dv1_y
            rng.uniform(-0.5, 0.5),          # dv1_z
            rng.uniform(1.0, 3.0),           # T1 (nondim, 1 unit ~ 4.3 days)
            rng.uniform(0.0, 1.0),           # T2
        ])
        try:
            sol = minimize(neg_obj, x0, method="Nelder-Mead",
                            options={"xatol": 1e-3, "fatol": 0.5,
                                      "maxiter": max_iter, "disp": False})
        except Exception:
            continue
        if sol.fun < 0:  # feasible mass found
            # Re-evaluate to get clean result
            res = evaluate(sol.x, udp, idE, idL, aE, eE, iE, aL, eL, iL)
            if res and res[0] != "infeasible":
                mass, row, dv_ms, _ = res
                if best is None or mass > best[0]:
                    best = (mass, row, dv_ms)
    dt = time.time() - t_start
    return best, dt


def main(test_pairs=None, n_starts=20, max_iter=100):
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    if test_pairs is None:
        test_pairs = [
            (0, 0),       # known coplanar — sanity
            (267, 185),   # GEO + inclined Moon (45° plane change)
            (294, 315),   # near-equatorial Earth + inclined Moon
            (155, 76),    # LEO + iL=1.50 polar Moon
            (265, 234),   # best Hohmann theoretical pair (apogee=43k km)
        ]

    for idE, idL in test_pairs:
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        print(f"\n=== Pair ({idE}, {idL}): aE={aE/1e3:.0f}km iE={iE:.2f}, "
              f"aL={aL/1e3:.0f}km iL={iL:.2f} ===", flush=True)
        best, dt = solve_pair_slsqp(udp, idE, idL,
                                       n_starts=n_starts, max_iter=max_iter,
                                       seed=hash((idE, idL)) % 2**32)
        if best:
            mass, row, dv_ms = best
            print(f"  BEST: mass={mass:.0f} kg, dv={dv_ms:.0f} m/s "
                  f"({n_starts} starts in {dt:.0f}s)", flush=True)
        else:
            print(f"  NO feasible in {dt:.0f}s ({n_starts} starts)", flush=True)


if __name__ == "__main__":
    main()
