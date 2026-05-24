"""Debug why solver fails for inclined Moon orbits.

Pair (294, 315) is most coplanar of failed: iE=0.02, iL=0.47 (27° plane change).
Hohmann + plane-change theoretical: ~460 kg.

Track what Lambert returns and how DC fails.
"""
import sys
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0, try_transfer
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv

udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
idE, idL = 294, 315
aE, eE, iE = udp.earth_data[idE]
aL, eL, iL = udp.moon_data[idL]
print(f"Pair ({idE},{idL}): aE={aE/1e3:.0f}km eE={eE:.3f} iE={iE:.3f}")
print(f"               aL={aL/1e3:.0f}km eL={eL:.3f} iL={iL:.3f}")
print(f"Plane change needed: ~{np.degrees(iL):.0f}° (Moon at iL from synodic XY)")

# Try a range of ea_dep, ea_arr, TOF and see what Lambert returns
print(f"\nLambert seed magnitudes (nondim, *1023 = m/s):")
print(f"{'tof':>5s} {'ea_dep':>7s} {'ea_arr':>7s} {'|dv0|nondim':>12s} "
      f"{'|dv0| m/s':>10s} {'r_arr_diff_km':>14s}")

best_seed = None
for tof_d in [5, 8, 11, 15]:
    tof = tof_d * 86400.0 / T
    for ea_dep in np.linspace(0, 2*np.pi, 4, endpoint=False):
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
        for ea_arr in np.linspace(0, 2*np.pi, 4, endpoint=False):
            pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
            dv0 = lambert_dv0(pv0, pv_tgt, tof)
            if dv0 is None:
                continue
            dv0_mag = np.linalg.norm(dv0)
            if not np.isfinite(dv0_mag):
                continue
            # Propagate to see arrival error
            pv_arr = propagate(pv0, 0.0, [dv0.tolist(), [0,0,0], [0,0,0]], [tof, 0.0])
            if len(pv_arr) == 0:
                r_err = "nan"
            else:
                r_arr = np.array(pv_arr[0])
                r_tgt_arr = np.array(pv_tgt[0])
                r_err = f"{np.linalg.norm(r_arr - r_tgt_arr) * L / 1e3:.0f}"
            print(f"{tof_d:>5d} {ea_dep:>7.3f} {ea_arr:>7.3f} "
                  f"{dv0_mag:>12.4f} {dv0_mag*V:>10.0f} {r_err:>14s}")
            if best_seed is None or (dv0_mag < best_seed[0] and dv0_mag*V < 6000):
                best_seed = (dv0_mag, dv0, tof_d, ea_dep, ea_arr, pv0, pv_tgt, tof)

if best_seed:
    print(f"\nBest seed: tof={best_seed[2]}d, ea=({best_seed[3]:.3f},{best_seed[4]:.3f}), "
          f"|dv0|={best_seed[0]*V:.0f}m/s")
    # Try DC with this seed
    pv0, pv_tgt, tof = best_seed[5], best_seed[6], best_seed[7]
    print(f"\nProbing 3-D DC with this seed:")
    res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                        dc_mode="3d", idE=idE, idL=idL)
    print(f"  3-D DC: {res}")
    res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                        dc_mode="6d", idE=idE, idL=idL)
    print(f"  6-D DC: {res}")
