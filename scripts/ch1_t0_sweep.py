"""Sweep t0 (Sun phase) for one inclined pair to see if it unlocks feasibility.

We've used t0=0 everywhere. Sun's gravity orientation rotates with t0.
For some t0 values, Sun perturbation might happen to compensate for the
Moon-gravity issue in the trajectory.
"""
import sys
import time
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
from scipy.optimize import least_squares

udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

# Pair with 5° inclination mismatch (failed before)
idE, idL = 27, 116
aE, eE, iE = udp.earth_data[idE]
aL, eL, iL = udp.moon_data[idL]
print(f"Pair ({idE},{idL}): iE={iE:.3f}, iL={iL:.3f}, |Δi|={abs(iE-iL):.3f}",
      flush=True)


def try_with_t0(t0, ea_dep, ea_arr, tof_d):
    """Try transfer with specified t0 and 3-D DC."""
    tof = tof_d * 86400.0 / T
    pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
    pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)

    dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
        return None
    if np.linalg.norm(dv0_seed) > 15:
        return None

    def residual(p):
        pv_a = propagate(pv0, t0, [p.tolist(), [0, 0, 0], [0, 0, 0]],
                          [tof, 0.0])
        if len(pv_a) == 0:
            return [100.0] * 3
        return [pv_a[0][0] - pv_tgt[0][0],
                pv_a[0][1] - pv_tgt[0][1],
                pv_a[0][2] - pv_tgt[0][2]]

    try:
        sol = least_squares(residual, dv0_seed, method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=50)
    except Exception:
        return None
    dv0 = sol.x
    pv_arr = propagate(pv0, t0, [dv0.tolist(), [0, 0, 0], [0, 0, 0]],
                        [tof, 0.0])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    return -f, (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V


print("\nSweep t0 × ea_dep × ea_arr × tof:", flush=True)
n_t0 = 6  # 0, π/3, 2π/3, π, 4π/3, 5π/3
n_total = 0
n_valid = 0
best = None
t_start = time.time()
for t0_val in np.linspace(0, 2 * np.pi, n_t0, endpoint=False):
    for ea_dep in np.linspace(0, 2 * np.pi, 6, endpoint=False):
        for ea_arr in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            for tof_d in [5, 8, 11]:
                n_total += 1
                res = try_with_t0(t0_val, ea_dep, ea_arr, tof_d)
                if res is not None:
                    n_valid += 1
                    mass, dv_ms = res
                    if best is None or mass > best[0]:
                        best = (mass, dv_ms, t0_val, ea_dep, ea_arr, tof_d)
                        print(f"  ✓ t0={t0_val:.2f} ea=({ea_dep:.2f},{ea_arr:.2f}) "
                              f"tof={tof_d}d: mass={mass:.0f}kg dv={dv_ms:.0f}m/s",
                              flush=True)

dt = time.time() - t_start
print(f"\n{n_total} ICs in {dt:.0f}s ({n_valid} valid)", flush=True)
if best:
    print(f"BEST: mass={best[0]:.0f}kg at t0={best[2]:.2f} ea=({best[3]:.2f},{best[4]:.2f}) tof={best[5]}d",
          flush=True)
else:
    print("Even t0 sweep didn't unlock feasibility for this inclined pair.", flush=True)
