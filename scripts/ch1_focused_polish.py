"""Focused: take v1 best IC (tof=10d, ea_dep=5.24, ea_arr=2.62) →
try 6-D DC. Should be ~5-15 sec, prove if 6-D drives mass ≥800kg."""

import sys
import time
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')

from esa_spoc_26.ch1_traj_proper_v2 import try_transfer
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state,
)

udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
aE, eE, iE = udp.earth_data[0]
aL, eL, iL = udp.moon_data[0]

ICs = [
    (10.0, 5.24, 2.62),   # v1 best
    (8.0, 5.24, 2.62),
    (10.0, 5.50, 2.50),
    (10.0, 5.00, 2.80),
    (12.0, 5.24, 2.62),
    (10.0, 4.71, 2.62),  # second-best in v1 scan
]

print("Pair (0,0): aE=6545km, aL=1838km", flush=True)
print(f"v1 best: 669kg @ (tof=10d, ea=(5.24, 2.62)), 3-D DC", flush=True)
print(f"Hohmann theoretical: ~864kg @ ~3962 m/s\n", flush=True)

for mode in ("3d", "6d"):
    print(f"\n=== {mode} DC ===", flush=True)
    for tof_d, ea_dep, ea_arr in ICs:
        tof = tof_d * 86400.0 / T
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
        pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
        t0 = time.time()
        res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                            aL, eL, iL, tof, dc_mode=mode, idE=0, idL=0)
        dt = time.time() - t0
        if res is None:
            print(f"  tof={tof_d:>4.1f}d ea=({ea_dep:.2f},{ea_arr:.2f}): "
                  f"FAIL in {dt:.1f}s", flush=True)
        else:
            mass, _, dv_ms = res
            print(f"  tof={tof_d:>4.1f}d ea=({ea_dep:.2f},{ea_arr:.2f}): "
                  f"mass={mass:>6.1f}kg dv={dv_ms:>5.0f}m/s in {dt:.1f}s",
                  flush=True)
