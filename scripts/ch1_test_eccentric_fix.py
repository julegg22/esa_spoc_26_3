"""Test the eccentric-orbit fix on previously-failed pairs.

Wires solve_arrival_eccentric into the try_transfer flow.
If our 3-D DC failures were because solve_arrival_dv rejected
valid-on-eccentric-orbit arrivals, this should unlock them.
"""
import sys
import time
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric
from scipy.optimize import least_squares


def try_transfer_v3(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                     idE=0, idL=0):
    """Lambert seed + 3-D DC + ECCENTRIC arrival solver."""
    dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
        return None
    if np.linalg.norm(dv0_seed) > 15:
        return None

    def residual(p):
        pv_a = propagate(pv0, 0.0, [p.tolist(), [0, 0, 0], [0, 0, 0]],
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
    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), [0, 0, 0], [0, 0, 0]],
                        [tof, 0.0])
    if len(pv_arr) == 0:
        return None
    # USE FIXED ECCENTRIC-AWARE ARRIVAL SOLVER
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
            *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
    return mass, row, dv_ms


udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

# Previously failed pairs + (0,0) sanity
test_pairs = [
    (0, 0),       # known coplanar circular — should still work
    (27, 116),    # LEO + eL=0.015 (slightly eccentric — bug's main target)
    (15, 78),     # LEO + eL=0.025
    (267, 181),   # GEO + eL=0.651 (highly eccentric — biggest gain expected!)
    (266, 234),   # GEO + eL=0.639
    (294, 315),   # near-equatorial + eL=0.0003 (essentially circular, no gain)
]

print("Testing eccentric-arrival fix on previously failed pairs:", flush=True)
for idE, idL in test_pairs:
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    print(f"\n=== Pair ({idE},{idL}): aE={aE/1e3:.0f}km iE={iE:.2f}, "
          f"aL={aL/1e3:.0f}km eL={eL:.3f} iL={iL:.2f} ===", flush=True)
    t0 = time.time()
    best = None
    n_valid = 0
    for tof_d in [5, 8, 11]:
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                res = try_transfer_v3(udp, pv0, pv_tgt, aE, eE, iE,
                                        aL, eL, iL, tof,
                                        idE=idE, idL=idL)
                if res is not None:
                    n_valid += 1
                    if best is None or res[0] > best[0]:
                        best = (res[0], res[2], tof_d, ea_dep, ea_arr)
                        print(f"  ✓ tof={tof_d}d ea=({ea_dep:.2f},{ea_arr:.2f}): "
                              f"mass={res[0]:.0f}kg dv={res[2]:.0f}m/s",
                              flush=True)
    dt = time.time() - t0
    if best:
        print(f"  BEST: mass={best[0]:.0f}kg dv={best[1]:.0f}m/s in {dt:.0f}s "
              f"({n_valid} valid)", flush=True)
    else:
        print(f"  STILL FAILS in {dt:.0f}s", flush=True)
