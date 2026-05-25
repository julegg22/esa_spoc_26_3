"""Hungarian-seeded sweep: solve EXACTLY the 400 pairs that the theoretical
Hungarian picks for max mass.

Strategy:
- Compute Hohmann theoretical mass matrix M[400×400].
- linear_sum_assignment(-M) → 400 (idE, idL) pairs with unique idE AND unique idL.
- Solve these 400 specific pairs.
- For pairs that fail (solver can't find feasibility), pick next-best (idL)
  that's still unique.

This GUARANTEES 400-transfer coverage if solver succeeds on each.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')

from ch1_production_sweep import _solve, _init, hohmann_lower_bound
from esa_spoc_26.ch1_trajectory import LtlTrajectory


def main(K_alternatives=5, n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/hungarian_seeded_results.json"):
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    aE_arr = udp.earth_data[:, 0]
    aL_arr = udp.moon_data[:, 0]
    eL_arr = udp.moon_data[:, 1]

    # Compute full Hohmann theoretical matrix
    print("Computing Hohmann theoretical 400x400 matrix...", flush=True)
    M = np.zeros((400, 400))
    for i in range(400):
        for j in range(400):
            m = hohmann_lower_bound(aE_arr[i], aL_arr[j])
            m_adj = m * (1 + eL_arr[j])
            M[i, j] = m_adj

    # Hungarian (best assignment)
    print("Hungarian on theoretical matrix...", flush=True)
    row_idx, col_idx = linear_sum_assignment(-M)
    primary_pairs = [(int(r), int(c)) for r, c in zip(row_idx, col_idx)]
    primary_sum = sum(M[r, c] for r, c in primary_pairs)
    print(f"Primary 400 pairs sum: {primary_sum:.0f} kg (theoretical)", flush=True)

    # Build candidate pool that preserves idL diversity:
    # always include the primary pair, plus K-1 alternative idLs ranked
    # by per-idE Hohmann ALSO accounting for "available" idLs not in primary set.
    pairs_with_alt = []
    primary_idL_set = set(c for _, c in primary_pairs)
    used_idL_count = np.zeros(400, dtype=int)
    for idE, primary_idL in primary_pairs:
        # Always add primary
        pairs_with_alt.append((idE, primary_idL))
        used_idL_count[primary_idL] += 1
        # Then K-1 alternatives, preferring idLs NOT in primary set (less contended)
        idL_scores = [(M[idE, j], j) for j in range(400)
                       if j != primary_idL]
        idL_scores.sort(reverse=True)
        added = 0
        # First pass: alternatives that are NOT in primary set
        for score, idL in idL_scores:
            if idL not in primary_idL_set and added < K_alternatives - 1:
                pairs_with_alt.append((idE, idL))
                used_idL_count[idL] += 1
                added += 1
        # If we couldn't fill from non-primary, fall back to any high-mass
        for score, idL in idL_scores:
            if added >= K_alternatives - 1:
                break
            if (idE, idL) not in pairs_with_alt:
                pairs_with_alt.append((idE, idL))
                used_idL_count[idL] += 1
                added += 1

    print(f"Candidate pool (incl. {K_alternatives} alternatives/idE): {len(pairs_with_alt)} pairs",
          flush=True)
    print(f"  idL coverage: {np.sum(used_idL_count > 0)}/400 distinct idLs", flush=True)
    print(f"  Estimated wall: {len(pairs_with_alt) * 40 / n_workers / 3600:.1f}h "
          f"on {n_workers} workers", flush=True)

    # Solve in parallel
    print(f"\nLaunching parallel solver...", flush=True)
    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_solve, pairs_with_alt, chunksize=2):
            n_done += 1
            if best is not None:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 20 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs_with_alt) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:3]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                ue = len(set(k[0] for k in results.keys()))
                ul = len(set(k[1] for k in results.keys()))
                print(f"  [{n_done:4d}/{len(pairs_with_alt)}] valid={n_valid} "
                      f"unique_idE={ue} unique_idL={ul} "
                      f"top=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 50 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_results).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_results).write_text(json.dumps(serializable))
    wall = time.time() - t_start
    ue = len(set(k[0] for k in results.keys()))
    ul = len(set(k[1] for k in results.keys()))
    print(f"\nDone in {wall:.0f}s: {n_valid}/{n_done} valid, "
          f"{ue} unique idE, {ul} unique idL", flush=True)
    print(f"Results saved to {out_results}", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K_alternatives=K, n_workers=nw)
