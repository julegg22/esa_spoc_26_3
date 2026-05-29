"""Evaluate all newly-discovered feasible pairs with the full solver.

After `ch1_full_matrix_scan.py` produces feasibility_matrix.json, this
script reads it, filters to (idE, idL) pairs NOT already in any
results file or the bank, and runs `try_bcp_apogee_3impulse` (with the
B6-fixed solver) on each. Saves to feasible_eval_results.json.

Then `ch1_hungarian_rebank_v2.py` can use this combined pool.
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
    """Reduced grid for fast mass evaluation."""
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


def main(n_workers=8,
          feasibility_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/feasibility_matrix.json",
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/feasible_eval_results.json"):
    udp = LtlTrajectory(ROOT)

    # Load feasibility matrix
    fmat = json.load(open(feasibility_path))
    feasible_pairs = []
    for k, v in fmat.items():
        if v[2]:  # feasible flag
            idE, idL = map(int, k.split(','))
            feasible_pairs.append((idE, idL))
    print(f"Feasibility matrix: {len(feasible_pairs)} feasibles "
          f"out of {len(fmat)}", flush=True)

    # Load already-tested pairs
    tested = set()
    rd = Path("/home/julian/Projects/esa_spoc_26_3/runs/ch1")
    for f in rd.glob("*results*.json"):
        try:
            d = json.load(open(f))
            for k in d.keys():
                ie, il = map(int, k.split(','))
                tested.add((ie, il))
        except Exception:
            pass
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        for i in range(0, len(dv), 21):
            if dv[i] >= 0:
                tested.add((int(dv[i]), int(dv[i + 1])))
    print(f"Already tested: {len(tested)} pairs", flush=True)

    # Filter to NEW feasibles
    new_pairs = [p for p in feasible_pairs if p not in tested]
    print(f"NEW feasibles to evaluate: {len(new_pairs)}", flush=True)
    print(f"Per-pair grid: 4×4×2×2×3=192 ICs. Est wall: "
          f"~{len(new_pairs) * 192 * 0.3 / n_workers / 60:.0f} min", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, new_pairs, chunksize=5):
            n_done += 1
            if best is not None and best[0] > 50:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 200 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(new_pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:5]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:5d}/{len(new_pairs)}] valid={n_valid} "
                      f"top5=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 500 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_path).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    print(f"\nFeasibles eval done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=nw)
