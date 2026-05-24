"""Final feasibility map: how many LEO+inclined-Moon pairs work with our solver?

If our Lambert+3D-DC works for LEO pairs with iL up to ~0.3 (17°),
we may have 100-300 feasible pairs in LEO×low-inclination-Moon.
Goal: 50 banked transfers × 800 kg = 40k kg minimum target.
"""
import sys
import time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import try_transfer
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state,
)

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _solve(args):
    idE, idL = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    t0 = time.time()
    # Coarse scan (8 ea_dep × 8 ea_arr × 3 TOFs = 192 ICs)
    for tof_d in (5, 8, 11):
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                     aL, eL, iL, tof,
                                     dc_mode="3d", idE=idE, idL=idL)
                if res is not None and (best is None or res[0] > best[0]):
                    best = (res[0], res[2], tof_d, float(ea_dep), float(ea_arr))
    dt = time.time() - t0
    return idE, idL, iE, iL, best, dt


def main():
    udp = LtlTrajectory(ROOT)
    iE_arr = udp.earth_data[:, 2]
    iL_arr = udp.moon_data[:, 2]
    eE_arr = udp.earth_data[:, 1]
    eL_arr = udp.moon_data[:, 1]
    aE_arr = udp.earth_data[:, 0]

    # Pick LEO pairs (aE < 10000 km) × Moon orbits with iL in various ranges
    leo_e = [i for i in range(400) if aE_arr[i] < 10e6 and eE_arr[i] < 0.05]
    print(f"LEO Earth orbits (a<10000km, e<0.05): {len(leo_e)}", flush=True)

    # Sample by iL bucket
    buckets = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.6), (0.6, 1.2)]
    pairs = []
    rng = np.random.default_rng(0)
    for lo, hi in buckets:
        ll = [j for j in range(400) if lo <= iL_arr[j] < hi and eL_arr[j] < 0.05]
        # Sample 3 from each bucket
        sample_l = rng.choice(ll, min(3, len(ll)), replace=False).tolist()
        # Pick 3 LEO Earth orbits with varying iE
        sample_e = rng.choice(leo_e, 3, replace=False).tolist()
        for e in sample_e:
            for l in sample_l:
                pairs.append((int(e), int(l)))
    print(f"Test pairs: {len(pairs)}", flush=True)

    print("Solving in parallel (8 workers, 192 ICs/pair, ~30-60s/pair)...\n", flush=True)
    t_start = time.time()
    results = []
    with mp.Pool(8, initializer=_init) as p:
        for idE, idL, iE, iL, best, dt in p.imap_unordered(_solve, pairs, chunksize=1):
            results.append((idE, idL, iE, iL, best, dt))
            if best:
                m, dv, tof_d, ea_d, ea_a = best
                print(f"  ✓ E{idE:3d}(iE={iE:.2f})→L{idL:3d}(iL={iL:.2f}): "
                      f"mass={m:.0f}kg dv={dv:.0f}m/s tof={tof_d}d in {dt:.0f}s",
                      flush=True)
            else:
                print(f"  ✗ E{idE:3d}(iE={iE:.2f})→L{idL:3d}(iL={iL:.2f}): "
                      f"FAIL in {dt:.0f}s", flush=True)

    wall = time.time() - t_start
    valid = [r for r in results if r[4] is not None]
    print(f"\n=== {len(valid)}/{len(results)} valid in {wall:.0f}s ===", flush=True)
    # Categorize by |Δi|
    if valid:
        for delta_i_bucket in [(0, 0.1), (0.1, 0.3), (0.3, 0.6), (0.6, 1.2)]:
            in_bucket = [r for r in valid if delta_i_bucket[0] <= abs(r[2] - r[3]) < delta_i_bucket[1]]
            if in_bucket:
                masses = [r[4][0] for r in in_bucket]
                print(f"  |Δi| {delta_i_bucket[0]:.1f}-{delta_i_bucket[1]:.1f}: "
                      f"{len(in_bucket)} pairs, median={np.median(masses):.0f}kg, max={max(masses):.0f}kg",
                      flush=True)


if __name__ == "__main__":
    main()
