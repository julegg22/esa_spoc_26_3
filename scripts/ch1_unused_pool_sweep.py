"""Expand pair pool: for each UNUSED idE, try its top-K best Moon orbits
to find a feasible transfer that ADDS to the bank.

Current bank uses 156 unique idE. 244 unused. For each unused idE, the
goal is to find at least one (idE, idL) where idL is also unused, giving
pure addition (no Hungarian swap).

Strategy:
- For each unused idE × ALL idL (excluding banked idLs), compute Hohmann
  theoretical mass.
- Pick top-K per unused idE (favor unused idLs for diversity).
- Solve all candidate pairs.
- Rebank.

Per-pair compute: 35s (same as production sweep).
700-1000 pairs total → 50-90 min on 8 workers.
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

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def main(K_per_unused_idE=3, n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/unused_pool_results.json"):
    udp = LtlTrajectory(ROOT)
    aE_arr = udp.earth_data[:, 0]
    aL_arr = udp.moon_data[:, 0]
    eL_arr = udp.moon_data[:, 1]

    # Identify used idE and idL from current bank
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    used_idE = set()
    used_idL = set()
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        for i in range(0, len(dv), 21):
            if dv[i] >= 0:
                used_idE.add(int(dv[i]))
                used_idL.add(int(dv[i + 1]))
    print(f"Bank uses {len(used_idE)} idE, {len(used_idL)} idL", flush=True)

    unused_e = [i for i in range(400) if i not in used_idE]
    unused_l = [j for j in range(400) if j not in used_idL]
    print(f"Unused: idE={len(unused_e)}, idL={len(unused_l)}", flush=True)

    # For each unused idE, prefer unused idLs (pure addition)
    print(f"Computing top-{K_per_unused_idE} idL per unused idE "
          f"(prefer unused)...", flush=True)
    pairs = []
    for idE in unused_e:
        # Score all idLs by Hohmann theoretical mass
        scores = []
        for idL in range(400):
            m = hohmann_lower_bound(aE_arr[idE], aL_arr[idL])
            m_adj = m * (1 + eL_arr[idL])
            # Bonus for unused idLs (diversification incentive)
            if idL not in used_idL:
                m_adj *= 1.3
            scores.append((m_adj, idL))
        scores.sort(reverse=True)
        for _, idL in scores[:K_per_unused_idE]:
            pairs.append((idE, idL))
    print(f"Candidate pairs: {len(pairs)}", flush=True)
    print(f"Estimated wall: ~{len(pairs) * 35 / n_workers / 3600:.1f}h "
          f"on {n_workers} workers", flush=True)

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
                ue = len(set(k[0] for k in results.keys()))
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"new_idE={ue} top=[{top_str}]kg "
                      f"wall={wall:.0f}s ETA={eta:.0f}s", flush=True)
            if n_done % 50 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_results).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_results).write_text(json.dumps(serializable))
    wall = time.time() - t_start
    ue = len(set(k[0] for k in results.keys()))
    print(f"\nDone in {wall:.0f}s: {n_valid}/{n_done} valid, "
          f"{ue} new unique idE", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K_per_unused_idE=K, n_workers=nw)
