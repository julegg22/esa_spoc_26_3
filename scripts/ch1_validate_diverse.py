"""Validate Lambert+3D-DC solver across diverse orbit regimes.

Picks 20 pairs spanning LEO/MEO/GEO Earth orbits × equatorial/polar Moon
orbits. Goal: confirm the solver is universal, not just lucky on (0,0).
Each pair: coarse grid scan (12×12×3 = 432 ICs ≈ 4 min single-thread).

No banking — diagnostic only.
"""
import sys
import time
import json
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


def _solve_one(args):
    idE, idL = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    t_start = time.time()
    for tof_d in (5, 8, 11):
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, 12, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                     aL, eL, iL, tof,
                                     dc_mode="3d", idE=idE, idL=idL)
                if res is not None and (best is None or res[0] > best[0]):
                    best = (res[0], res[2], tof_d,
                             float(ea_dep), float(ea_arr))
    dt = time.time() - t_start
    return idE, idL, aE, aL, iE, iL, best, dt


def main():
    udp = LtlTrajectory(ROOT)
    e_a = udp.earth_data[:, 0]
    e_i = udp.earth_data[:, 2]
    m_a = udp.moon_data[:, 0]
    m_i = udp.moon_data[:, 2]

    # Buckets
    leo = np.where(e_a < 10e6)[0]
    meo = np.where((e_a >= 10e6) & (e_a < 30e6))[0]
    geo = np.where(e_a >= 30e6)[0]
    print(f"Earth buckets: LEO={len(leo)}, MEO={len(meo)}, GEO+={len(geo)}",
          flush=True)
    print(f"Moon i range: 0–{m_i.max():.2f} rad", flush=True)

    rng = np.random.default_rng(42)
    # Sample 8 LEO, 6 MEO, 6 GEO (or as available)
    e_sample = list(rng.choice(leo, min(8, len(leo)), replace=False))
    e_sample += list(rng.choice(meo, min(6, len(meo)), replace=False))
    e_sample += list(rng.choice(geo, min(6, len(geo)), replace=False))
    e_sample = sorted(int(e) for e in e_sample)
    # For each Earth, pick a Moon orbit with varied inclination
    l_sample = sorted(rng.choice(400, 20, replace=False).tolist())
    pairs = list(zip(e_sample, l_sample))
    print(f"\nTesting {len(pairs)} pairs:", flush=True)
    for e, l in pairs:
        print(f"  E{e:3d} (a={e_a[e]/1e3:.0f}km i={e_i[e]:.2f}) "
              f"→ L{l:3d} (a={m_a[l]/1e3:.0f}km i={m_i[l]:.2f})",
              flush=True)

    print("\nSolving...", flush=True)
    t0 = time.time()
    results = []
    with mp.Pool(8, initializer=_init) as p:
        for idE, idL, aE, aL, iE, iL, best, dt in p.imap_unordered(
                _solve_one, pairs, chunksize=1):
            if best is None:
                print(f"  E{idE:3d}→L{idL:3d} (aE={aE/1e3:.0f}km iE={iE:.2f},"
                      f" aL={aL/1e3:.0f}km iL={iL:.2f}): "
                      f"FAIL in {dt:.0f}s", flush=True)
                results.append((idE, idL, aE, iE, aL, iL, None))
            else:
                mass, dv_ms, tof_d, ea_d, ea_a = best
                print(f"  E{idE:3d}→L{idL:3d} (aE={aE/1e3:.0f}km iE={iE:.2f},"
                      f" aL={aL/1e3:.0f}km iL={iL:.2f}): "
                      f"mass={mass:>6.1f}kg dv={dv_ms:>5.0f}m/s "
                      f"tof={tof_d}d in {dt:.0f}s", flush=True)
                results.append((idE, idL, aE, iE, aL, iL, best))
    wall = time.time() - t0

    # Summary
    valid = [r for r in results if r[6] is not None]
    print(f"\n=== Summary: {len(valid)}/{len(results)} valid in {wall:.0f}s ===",
          flush=True)
    if valid:
        masses = [r[6][0] for r in valid]
        print(f"  Mass: min={min(masses):.0f}, max={max(masses):.0f}, "
              f"median={np.median(masses):.0f}, sum={sum(masses):.0f}kg",
              flush=True)
        # By regime
        for bucket_name, bucket_e in (("LEO", leo), ("MEO", meo), ("GEO", geo)):
            in_bucket = [r for r in valid if r[0] in bucket_e]
            if in_bucket:
                ms = [r[6][0] for r in in_bucket]
                print(f"  {bucket_name}: n={len(in_bucket)}, median={np.median(ms):.0f}kg, "
                      f"max={max(ms):.0f}kg", flush=True)

    # Persist
    out_path = "/home/julian/Projects/esa_spoc_26_3/runs/ch1/19_validate_diverse.json"
    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump([{"idE": r[0], "idL": r[1], "aE_km": r[2]/1e3,
                     "iE": r[3], "aL_km": r[4]/1e3, "iL": r[5],
                     "mass_kg": r[6][0] if r[6] else None,
                     "dv_ms": r[6][1] if r[6] else None,
                     "tof_d": r[6][2] if r[6] else None}
                    for r in results], f, indent=2)
    print(f"\nResults saved to {out_path}", flush=True)


if __name__ == "__main__":
    main()
