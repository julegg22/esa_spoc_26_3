"""Expand v4: idE+idL diversity via quintile sampling.

v2 saturated at 11 unique unused idEs × 3 unused idLs (idL-biased scoring).
v3 saturated at 3 unique unused idEs × ~40 unused idLs (Hohmann-biased toward
smallest unused aE).

v4 fix: for each unused idL, pick K=5 unused idEs SAMPLED across aE quintiles
of the unused-idE pool. This covers LEO/MEO/GEO unused families simultaneously.
Goal: uE >> 20, uL >> 40, allowing Hungarian to add 20-50 new transfers.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')

from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _task(args):
    idE, idL = args
    udp = _UDP[0]
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 6, endpoint=False):
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi):
                for t0_val in (0.0, np.pi):
                    for ea_arr in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                        for t2_d in (0.3, 0.7, 1.2):
                            res = try_bcp_apogee_3impulse(
                                udp, idE, idL, raan_e, argp_e, ea_dep,
                                t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                            if res is not None and (best is None or res[0] > best[0]):
                                best = res
    return idE, idL, best


def main(K=5, n_workers=8,
          out_results="/home/julian/Projects/esa_spoc_26_3/runs/ch1/bcp_apogee_expand_v4_results.json"):
    udp = LtlTrajectory(ROOT)
    aE_arr = udp.earth_data[:, 0]

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
    print(f"Bank: {len(used_idE)} idE, {len(used_idL)} idL", flush=True)

    unused_e = sorted([i for i in range(400) if i not in used_idE],
                       key=lambda i: aE_arr[i])
    unused_l = [i for i in range(400) if i not in used_idL]
    print(f"Unused: {len(unused_e)} idE, {len(unused_l)} idL", flush=True)

    # Quintile-sample K idEs across aE range — covers LEO..GEO unused
    n_ue = len(unused_e)
    quantile_idx = [int((i + 0.5) * n_ue / K) for i in range(K)]
    sampled_idE = [unused_e[q] for q in quantile_idx]
    print(f"Sampled {K} unused idEs (aE quintile-sampled):", flush=True)
    for e in sampled_idE:
        print(f"  idE={e:3d} aE={aE_arr[e]:.3e}", flush=True)

    # Each unused idL tries each sampled idE — full grid for max diversity
    pairs = []
    for idL in unused_l:
        for idE in sampled_idE:
            pairs.append((idE, idL))
    print(f"Candidates: {len(pairs)} pairs ({len(unused_l)} idL × {K} idE)",
           flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=1):
            n_done += 1
            if best is not None:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 10 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                ue = len(set(k[0] for k in results.keys()))
                ul = len(set(k[1] for k in results.keys()))
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:3]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"uE={ue} uL={ul} top=[{top_str}]kg "
                      f"wall={wall:.0f}s ETA={eta:.0f}s", flush=True)
            if n_done % 30 == 0:
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
          f"{ue} unused idE, {ul} unused idL covered", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K=K, n_workers=nw)
