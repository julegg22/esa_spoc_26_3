"""Continuous polish on (ea_dep, ea_arr, TOF) for pair (0,0).

Hypothesis: the 670 kg v1 result was a coarse grid point. Polishing
the 3 continuous IC parameters with Nelder-Mead should push mass higher
because the optimum likely sits BETWEEN grid points.
"""
import sys
import time
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import try_transfer
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state,
)

udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
aE, eE, iE = udp.earth_data[0]
aL, eL, iL = udp.moon_data[0]

# v1 best IC
x0 = np.array([10.0, 5.24, 2.62])  # (tof_d, ea_dep, ea_arr)
print(f"Start IC: tof={x0[0]}d, ea_dep={x0[1]}, ea_arr={x0[2]}", flush=True)

# Trace evaluations
hist = []

def neg_mass(p):
    tof_d, ea_dep, ea_arr = p
    if tof_d < 2 or tof_d > 25:
        return 0.0
    tof = tof_d * 86400.0 / T
    pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
    pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
    res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL,
                        tof, dc_mode="3d", idE=0, idL=0)
    if res is None:
        return 0.0
    mass = res[0]
    hist.append((mass, tof_d, ea_dep, ea_arr))
    if len(hist) % 5 == 0:
        best = max(hist, key=lambda h: h[0])
        print(f"  [{len(hist)} evals] best={best[0]:.1f}kg @ "
              f"tof={best[1]:.2f}d ea=({best[2]:.3f},{best[3]:.3f})",
              flush=True)
    return -mass

print("\nNelder-Mead polish starting...", flush=True)
t0 = time.time()
sol = minimize(neg_mass, x0, method="Nelder-Mead",
                options={"xatol": 1e-3, "fatol": 0.5,
                          "maxiter": 100, "disp": True,
                          "initial_simplex": np.array([
                              [10.0, 5.24, 2.62],
                              [10.5, 5.24, 2.62],
                              [10.0, 5.34, 2.62],
                              [10.0, 5.24, 2.72],
                          ])})
dt = time.time() - t0

best = max(hist, key=lambda h: h[0]) if hist else None
print(f"\n=== Polish done in {dt:.0f}s, {len(hist)} evals ===", flush=True)
if best:
    print(f"BEST mass={best[0]:.1f}kg @ tof={best[1]:.2f}d "
          f"ea=({best[2]:.3f},{best[3]:.3f})", flush=True)
    print(f"\nGap to Hohmann 864kg: {864-best[0]:.0f}kg "
          f"(80% target: 691kg, 90% target: 778kg)", flush=True)
else:
    print("NO valid solutions found", flush=True)
