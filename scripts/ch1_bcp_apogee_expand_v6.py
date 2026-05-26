"""Expand v6: pair every unused idE with every favorable Moon idL.

Insight from v2/v3 analysis: 42 unused Moon idLs have signature (aL > 4.5e6,
eL > 0.4) — the "apogee-favorable" cluster where BCP-apogee 3-impulse
naturally lands. These are the highest-value targets for new transfers.

Approach: cross-product 236 unused idE × 42 favorable idL = 9912 pairs.
Use REDUCED grid (~24 evals/pair vs full 288) for fast screening. Winners
(mass > 100 kg) survive to Hungarian rebank.

Reduced grid: 4 raan × 1 argp × 1 ea_dep × 1 t0 × 3 ea_arr × 2 t2_d = 24.
Cost: 9912 pairs × ~4 sec/pair / 8 workers = 5000 sec ~= 80 min.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
from esa_spoc_26.ch1_trajectory import LtlTrajectory

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _task(args):
    """Reduced grid — fast screen."""
    idE, idL = args
    udp = _UDP[0]
    best = None
    # 4 raan × 1 argp × 1 ea_dep × 1 t0 × 3 ea_arr × 2 t2_d = 24 evals
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for ea_arr in (0.0, np.pi, np.pi / 2):
            for t2_d in (0.5, 1.0):
                res = try_bcp_apogee_3impulse(
                    udp, idE, idL, raan_e, 0.0, 0.0,
                    0.0, 0.0, 0.0, ea_arr, t2_d=t2_d)
                if res is not None and (best is None or res[0] > best[0]):
                    best = res
    return idE, idL, best


def main(n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/bcp_apogee_expand_v6_results.json"):
    udp = LtlTrajectory(ROOT)
    aL_arr = udp.moon_data[:, 0]
    eL_arr = udp.moon_data[:, 1]

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

    unused_e = [i for i in range(400) if i not in used_idE]
    # 42 favorable: aL > 4.5e6 AND eL > 0.4 AND not in bank
    favorable_l = [l for l in range(400)
                    if l not in used_idL
                    and aL_arr[l] > 4.5e6 and eL_arr[l] > 0.4]
    print(f"Bank: {len(used_idE)} idE, {len(used_idL)} idL", flush=True)
    print(f"Unused idE: {len(unused_e)}, Favorable unused idL: {len(favorable_l)}",
           flush=True)

    pairs = [(idE, idL) for idE in unused_e for idL in favorable_l]
    print(f"Candidates: {len(pairs)} pairs", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=5):
            n_done += 1
            if best is not None and best[0] > 50:  # noise filter
                n_valid += 1
                key = (idE, idL)
                if key not in results or results[key][0] < best[0]:
                    results[key] = best
            if n_done % 100 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                ue = len(set(k[0] for k in results.keys()))
                ul = len(set(k[1] for k in results.keys()))
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:3]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:5d}/{len(pairs)}] valid={n_valid} "
                      f"uE={ue} uL={ul} top=[{top_str}]kg "
                      f"wall={wall:.0f}s ETA={eta:.0f}s", flush=True)
            if n_done % 500 == 0:
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
          f"{ue} unused idE, {ul} unused idL", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=nw)
