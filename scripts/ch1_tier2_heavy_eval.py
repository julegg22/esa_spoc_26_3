"""TIER 2: heavy 3-impulse eval on top Tier-1 candidates.

Takes the top-N candidates from Tier 1 light results and runs the full
3-impulse DC architecture (try_bcp_apogee_3impulse with ~192 ICs/pair).
This typically gives 5-30% mass improvement over the 2-impulse light eval
for pairs where the trajectory geometry allows mid-burn refinement.

Per-pair ~60 sec wall. For top-1500 / 8 workers = ~3 hours.

Output: tier2_heavy_results.json. Combine with Tier 1 + existing → rebank.
"""
import sys
import time
import json
import math
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _task(args):
    """4×4×2×2×3 = 192 ICs/pair with full DC."""
    idE, idL = args
    udp = _UDP[0]
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
            for t0 in (0.0, np.pi):
                for ea_arr in (0.0, np.pi):
                    for t2_d in (0.5, 2.0, 4.0):
                        res = try_bcp_apogee_3impulse(
                            udp, idE, idL, raan_e, 0.0, ea_dep,
                            t0, 0.0, 0.0, ea_arr, t2_d=t2_d)
                        if res is not None and (best is None or res[0] > best[0]):
                            best = res
    return idE, idL, best


def main(n_workers=8, top_n=1500,
          tier1_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/tier1_light_results.json",
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/tier2_heavy_results.json"):
    udp = LtlTrajectory(ROOT)
    tier1 = json.load(open(tier1_path))
    # Sort by Tier 1 mass descending, take top N
    items = sorted(tier1.items(), key=lambda kv: -kv[1][0])[:top_n]
    pairs = [(int(k.split(',')[0]), int(k.split(',')[1])) for k, _ in items]
    print(f"Tier 1 had {len(tier1)} candidates; Tier 2 polishes top {len(pairs)}",
           flush=True)
    print(f"Tier 1 mass range of selected: {items[0][1][0]:.0f} → {items[-1][1][0]:.0f} kg",
           flush=True)
    print(f"Per-pair grid 192 ICs × ~0.3 sec. Est wall: "
          f"~{len(pairs) * 192 * 0.3 / n_workers / 60:.0f} min", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=2):
            n_done += 1
            if best is not None and best[0] > 50:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 50 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:5]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"top5=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 200 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_path).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    print(f"\nTier 2 done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    main(n_workers=nw, top_n=top_n)
