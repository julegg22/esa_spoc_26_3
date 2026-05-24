"""Quick test: for ONE inclined pair, does sweeping RAAN_E unlock feasibility?

Hypothesis: prior sweeps hardcoded RAAN=0 → orbital planes mis-aligned for
inclined Moon orbits. Adding RAAN_E grid should fix it.
"""
import sys
import time
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import try_transfer
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state,
)

udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

# Pick the most promising inclined pair: GEO Earth (aE=42449km, iE=0.10) + Moon (aL=5280km, iL=0.55)
# Theoretical Hohmann + plane change ~ 2200 m/s → ~1700 kg expected
idE, idL = 267, 185
aE, eE, iE = udp.earth_data[idE]
aL, eL, iL = udp.moon_data[idL]
print(f"Pair ({idE}, {idL}): aE={aE/1e3:.0f}km iE={iE:.3f} (GEO)", flush=True)
print(f"                    aL={aL/1e3:.0f}km iL={iL:.3f}", flush=True)
print(f"|Δi|={abs(iE-iL):.2f} rad", flush=True)
print(f"Theoretical Hohmann + plane change ~ 2200 m/s → ~1700 kg expected\n", flush=True)

# Search: RAAN_E × ea_dep × ea_arr × tof_d
# Goal: find ANY feasible point — small grid, fast
n_total = 0
n_valid = 0
best = None
t0 = time.time()
for raan_e in np.linspace(0, 2*np.pi, 8, endpoint=False):
    for ea_dep in np.linspace(0, 2*np.pi, 6, endpoint=False):
        pv0 = earth_orbit_state(aE, eE, iE, raan_e, 0.0, ea_dep)
        for ea_arr in np.linspace(0, 2*np.pi, 6, endpoint=False):
            pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
            for tof_d in [4, 6, 9, 13]:
                tof = tof_d * 86400.0 / T
                n_total += 1
                res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                     aL, eL, iL, tof,
                                     dc_mode="3d", idE=idE, idL=idL)
                if res is not None:
                    n_valid += 1
                    mass, _, dv_ms = res
                    if best is None or mass > best[0]:
                        best = (mass, dv_ms, raan_e, ea_dep, ea_arr, tof_d)
                        print(f"  ✓ raan_e={raan_e:.2f} ea_dep={ea_dep:.2f} "
                              f"ea_arr={ea_arr:.2f} tof={tof_d}d: "
                              f"mass={mass:.0f}kg dv={dv_ms:.0f}m/s",
                              flush=True)
        if (n_total % 100) == 0:
            print(f"  ... {n_total} ICs done, {n_valid} valid, elapsed {time.time()-t0:.0f}s",
                  flush=True)

dt = time.time() - t0
print(f"\n=== {n_total} ICs in {dt:.0f}s, {n_valid} valid ===", flush=True)
if best:
    mass, dv_ms, raan_e, ea_dep, ea_arr, tof_d = best
    print(f"BEST: mass={mass:.0f}kg dv={dv_ms:.0f}m/s "
          f"@ raan_e={raan_e:.2f} ea_dep={ea_dep:.2f} ea_arr={ea_arr:.2f} tof={tof_d}d",
          flush=True)
else:
    print("NO feasible — RAAN_E sweep didn't unlock this inclined pair.", flush=True)
