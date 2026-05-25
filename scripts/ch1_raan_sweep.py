"""Tier 2: raan_e sweep to unlock additional pair feasibilities.

Currently 159 unique idL in our results (241 unused). For each unused idL,
try multiple (idE, raan_e) combinations to find feasibility.

Strategy:
- For each unused idL, pick top-K candidate idE by Hohmann theoretical.
- For each (idE, idL): sweep raan_e in 6 values × 8 ea_dep × 8 ea_arr × 3 tof.
- Capture any new feasible pairs.

The raan_e degree of freedom rotates the Earth orbit plane, helping
inclined-Moon-orbit targets that the raan=0 solver can't reach.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')

from ch1_production_sweep import _try_transfer, hohmann_lower_bound
from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state,
)

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"

_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _solve_raan(args):
    """Per-pair sweep over raan_e × ea_dep × ea_arr × tof."""
    idE, idL = args
    if _UDP[0] is None:
        _init()
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    # Smaller grid: 4 raan × 5 ea_dep × 5 ea_arr × 2 tofs = 200 ICs (vs 648)
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for tof_d in (5, 9):
            tof = tof_d * 86400.0 / T
            for ea_dep in np.linspace(0, 2 * np.pi, 5, endpoint=False):
                pv0 = earth_orbit_state(aE, eE, iE, raan_e, 0.0, ea_dep)
                for ea_arr in np.linspace(0, 2 * np.pi, 5, endpoint=False):
                    pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                    res = _try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                          aL, eL, iL, tof, idE, idL)
                    if res is not None and (best is None or res[0] > best[0]):
                        best = res
    return idE, idL, best


def main(K_per_unused_idL=3, n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/raan_results.json"):
    udp = LtlTrajectory(ROOT)
    aE_arr = udp.earth_data[:, 0]
    aL_arr = udp.moon_data[:, 0]
    eL_arr = udp.moon_data[:, 1]

    # Load existing results to identify unused idLs
    used_idL = set()
    for jpath in ["runs/ch1/hungarian_seeded_results.json",
                   "runs/ch1/smart_coverage_results.json",
                   "runs/ch1/sweep_results.json"]:
        try:
            data = json.load(open(jpath))
            for k in data.keys():
                _, idL = map(int, k.split(','))
                used_idL.add(idL)
        except Exception:
            pass

    unused_idL = [j for j in range(400) if j not in used_idL]
    print(f"Used idL: {len(used_idL)}, Unused: {len(unused_idL)}", flush=True)

    # For each unused idL, pick top-K candidate idE by Hohmann theoretical
    print(f"Computing top-{K_per_unused_idL} idE per unused idL...", flush=True)
    pairs = []
    for idL in unused_idL:
        candidates = []
        for idE in range(400):
            m = hohmann_lower_bound(aE_arr[idE], aL_arr[idL])
            m_adj = m * (1 + eL_arr[idL])
            candidates.append((m_adj, idE))
        candidates.sort(reverse=True)
        for _, idE in candidates[:K_per_unused_idL]:
            pairs.append((idE, idL))
    print(f"Candidate pairs: {len(pairs)}", flush=True)
    # Per pair takes longer (6x more ICs than basic sweep)
    print(f"Estimated wall: ~{len(pairs) * 200 / n_workers / 3600:.1f}h "
          f"on {n_workers} workers (6x ICs per pair)", flush=True)

    print(f"\nLaunching parallel solver...", flush=True)
    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_solve_raan, pairs, chunksize=2):
            n_done += 1
            if best is not None:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 10 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                ul = len(set(k[1] for k in results.keys()))
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:3]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"unique_idL={ul} top=[{top_str}]kg "
                      f"wall={wall:.0f}s ETA={eta:.0f}s", flush=True)
            if n_done % 30 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_results).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_results).write_text(json.dumps(serializable))
    wall = time.time() - t_start
    ul = len(set(k[1] for k in results.keys()))
    print(f"\nDone in {wall:.0f}s: {n_valid}/{n_done} valid, "
          f"{ul} new unique idL unlocked", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K_per_unused_idL=K, n_workers=nw)
