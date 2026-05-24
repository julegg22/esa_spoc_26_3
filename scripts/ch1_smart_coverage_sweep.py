"""Smart-coverage sweep: force idE diversity to expand Hungarian pool.

Current bank uses 20 GEO Earth orbits (all of them). 380 Earth orbits
(21 MEO + 359 LEO) are UNUSED. Hohmann-ranking favors GEO, so even
top-2000 by mass-rank don't include MEO/LEO.

Strategy:
- For each of the 380 unused idE, pick top-K best (idL) by Hohmann
  theoretical mass with this idE specifically.
- This gives 380*K candidates with FORCED idE diversity.
- After solving them, Hungarian can pick the actually-best per idE.

Default K=3 → 1140 pairs.
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


def main(K_per_idE=3, n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/smart_coverage_results.json"):
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    aE_arr = udp.earth_data[:, 0]
    aL_arr = udp.moon_data[:, 0]
    eL_arr = udp.moon_data[:, 1]

    # Identify currently-used idE from bank
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    used_e = set()
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        for i in range(0, len(dv), 21):
            if dv[i] >= 0:
                used_e.add(int(dv[i]))
    print(f"Currently used idE: {len(used_e)}", flush=True)

    unused_e = [i for i in range(400) if i not in used_e]
    print(f"Unused idE: {len(unused_e)}", flush=True)

    # For each unused idE, pick top-K best (idL) by Hohmann theoretical
    print(f"Computing top-{K_per_idE} idL per unused idE...", flush=True)
    pairs = []
    for idE in unused_e:
        candidates = []
        for idL in range(400):
            m = hohmann_lower_bound(aE_arr[idE], aL_arr[idL])
            m_adjusted = m * (1 + eL_arr[idL])
            candidates.append((m_adjusted, idL))
        candidates.sort(reverse=True)
        for m, idL in candidates[:K_per_idE]:
            pairs.append((idE, idL))
    print(f"Total candidate pairs: {len(pairs)}", flush=True)
    # Estimate compute
    est_h = len(pairs) * 40 / n_workers / 3600
    print(f"Estimated wall: {est_h:.1f}h on {n_workers} workers", flush=True)

    print(f"\nLaunching parallel solver...", flush=True)
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
                # Count unique idE
                ue = len(set(k[0] for k in results.keys()))
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} unique_idE={ue} "
                      f"top=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)

            # Periodic save (every 30 pairs)
            if n_done % 30 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_results).write_text(json.dumps(serializable))

    # Final save
    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_results).write_text(json.dumps(serializable))
    wall = time.time() - t_start
    unique_e = len(set(k[0] for k in results.keys()))
    print(f"\nDone in {wall:.0f}s: {n_valid}/{n_done} valid, {unique_e} unique idE",
          flush=True)
    print(f"Results saved to {out_results}", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K_per_idE=K, n_workers=nw)
