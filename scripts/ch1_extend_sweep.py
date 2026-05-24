"""Tier 1C: extend sweep to next 1500 (pairs #500-#2000 by Hohmann).

After the top-500 sweep + polish completes, this script broadens the
Hungarian candidate pool. More candidates → better unique-triple assignment.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')

from ch1_production_sweep import _solve, _init, hohmann_lower_bound
from esa_spoc_26.ch1_trajectory import LtlTrajectory


def main(start_rank=500, end_rank=2000, n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/extended_results.json"):
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    aE = udp.earth_data[:, 0]
    aL = udp.moon_data[:, 0]
    eL = udp.moon_data[:, 1]

    print(f"Pre-computing Hohmann ranking for all 160000 pairs...", flush=True)
    flat = []
    for i in range(400):
        for j in range(400):
            m = hohmann_lower_bound(aE[i], aL[j])
            m_adjusted = m * (1 + eL[j])
            flat.append((m_adjusted, i, j))
    flat.sort(reverse=True)
    pairs = [(i, j) for m, i, j in flat[start_rank:end_rank]]
    print(f"Selected pairs ranked #{start_rank}-#{end_rank}: "
          f"top {flat[start_rank][0]:.0f} kg, bottom {flat[end_rank-1][0]:.0f} kg",
          flush=True)

    print(f"\nLaunching parallel solver ({n_workers} workers)...", flush=True)
    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_solve, pairs, chunksize=2):
            n_done += 1
            if best is not None:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 10 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:3]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"top=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)

            # Periodic save (every 50 pairs)
            if n_done % 50 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_results).write_text(json.dumps(serializable))

    # Final save
    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_results).write_text(json.dumps(serializable))
    print(f"\nDone: {n_valid}/{n_done} valid in {time.time()-t_start:.0f}s",
          flush=True)
    print(f"Results saved to {out_results}", flush=True)


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    main(start_rank=start, end_rank=end, n_workers=nw)
