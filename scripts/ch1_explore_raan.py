"""For pair (294, 315) inclined: scan ALL 3 angular DOF (RAAN, argp, ea) for Earth orbit
+ (RAAN, argp, ea) for Moon arrival point. See if feasibility appears when planes are
node-aligned via RAAN choice.

Hypothesis: hardcoding RAAN=0 in all prior sweeps killed inclined-pair feasibility
because the orbital planes don't share a line of nodes.
"""
import sys
import time
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0, try_transfer
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv

udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

# Try multiple inclined pairs
test_pairs = [
    (294, 315),  # iE=0.02, iL=0.47
    (155, 76),   # iE=0.08, iL=1.50
    (266, 173),  # iE=0.23, iL=0.76 (GEO)
    (267, 185),  # iE=0.10, iL=0.55 (GEO)
]

print("Scanning RAAN_E + ea_dep + RAAN_L + ea_arr (4-D grid)", flush=True)
print("RAAN=0 was hardcoded in all prior sweeps — testing if RAAN unlocks inclined pairs", flush=True)
print()

for idE, idL in test_pairs:
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    plane_angle = abs(iE - iL)
    print(f"\n=== Pair ({idE}, {idL}): iE={iE:.2f}, iL={iL:.2f}, |Δi|={plane_angle:.2f} ===",
          flush=True)
    t0 = time.time()
    best = None
    n_tried = 0
    n_valid = 0
    # 4-D scan: RAAN_E, ea_dep, RAAN_L, ea_arr
    for raan_e in np.linspace(0, 2*np.pi, 6, endpoint=False):
        for ea_dep in np.linspace(0, 2*np.pi, 8, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, raan_e, 0.0, ea_dep)
            for raan_l in np.linspace(0, 2*np.pi, 6, endpoint=False):
                for ea_arr in np.linspace(0, 2*np.pi, 8, endpoint=False):
                    for tof_d in [5, 8, 11]:
                        tof = tof_d * 86400.0 / T
                        pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, 0.0, ea_arr)
                        n_tried += 1
                        res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                            aL, eL, iL, tof,
                                            dc_mode="3d", idE=idE, idL=idL)
                        if res is not None:
                            n_valid += 1
                            mass, _, dv_ms = res
                            if best is None or mass > best[0]:
                                best = (mass, dv_ms, raan_e, ea_dep,
                                        raan_l, ea_arr, tof_d)
                                print(f"  ✓ raan_e={raan_e:.2f} ea_dep={ea_dep:.2f} "
                                      f"raan_l={raan_l:.2f} ea_arr={ea_arr:.2f} "
                                      f"tof={tof_d}d: mass={mass:.0f}kg dv={dv_ms:.0f}m/s",
                                      flush=True)
    dt = time.time() - t0
    print(f"  Scanned {n_tried} ICs in {dt:.0f}s, {n_valid} valid", flush=True)
    if best:
        mass, dv_ms, raan_e, ea_dep, raan_l, ea_arr, tof_d = best
        print(f"  BEST: mass={mass:.0f}kg, dv={dv_ms:.0f}m/s "
              f"@ raan_e={raan_e:.2f} ea_dep={ea_dep:.2f} "
              f"raan_l={raan_l:.2f} ea_arr={ea_arr:.2f} tof={tof_d}d",
              flush=True)
    else:
        print(f"  NO feasible found", flush=True)
