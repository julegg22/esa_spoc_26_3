"""Tier 1A v2 — focused Sun-assist probe, smaller grid.

v1 estimated 54h for 2304 ICs/pair × 2250 pairs. Too long.

v2 fix: smaller per-pair grid (128 ICs vs 2304) focused on the
*specific* extensions hypothesized to unlock Sun-assist:
- t_max_d ∈ {25, 45, 60}  — long-TOF Sun perturbation
- t2_d ∈ {2, 6, 12, 20}  — long-coast (vs polish's 5 ceiling)
- raan_e: 4 values, ea_dep: 2, t0: 2

128 ICs/pair × 2250 pairs × 0.3 sec / 8 workers = 21,600 sec = 6 hours.
Overnight, with periodic checkpoints.
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
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, MU_EARTH

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _task(args):
    """Smaller grid: 4 × 2 × 2 × 3 × 4 = 192 ICs/pair (NEW grid axes)."""
    idE, idL = args
    udp = _UDP[0]
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for ea_dep in (0.0, np.pi):
            for t0_val in (0.0, np.pi):
                for t_max_d in (25.0, 45.0, 60.0):  # LONG TOF — Sun-assist
                    for t2_d in (2.0, 6.0, 12.0, 20.0):  # LONG COAST
                        res = try_bcp_apogee_3impulse(
                            udp, idE, idL, raan_e, 0.0, ea_dep,
                            t0_val, 0.0, 0.0, 0.0,
                            t2_d=t2_d, t_max_d=t_max_d)
                        if res is not None and (best is None or res[0] > best[0]):
                            best = res
    return idE, idL, best


def main(n_workers=8, K=15,
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/tier1a_v2_results.json"):
    udp = LtlTrajectory(ROOT)
    aE = udp.earth_data[:, 0]
    iE = udp.earth_data[:, 2]
    aL = udp.moon_data[:, 0]
    eL = udp.moon_data[:, 1]
    iL = udp.moon_data[:, 2]

    high_el = [l for l in range(400) if aL[l] > 3e6 and eL[l] > 0.4]
    print(f"High-eL Moon orbits: {len(high_el)}", flush=True)

    R_MOON_SI = 384400e3
    pairs = set()
    for idL in high_el:
        scores = []
        r_apo_l = aL[idL] * (1.0 + eL[idL])
        v_target_apo = math.sqrt(4.9028e12 * (1.0 - eL[idL]) / r_apo_l)
        for idE in range(400):
            if aE[idE] > 1.5e7:
                continue
            r0 = aE[idE]
            a_t = 0.5 * (r0 + R_MOON_SI)
            v_peri = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
            v0 = math.sqrt(MU_EARTH / r0)
            dv_h = v_peri - v0
            dv_p = 2 * v_target_apo * math.sin(abs(iE[idE] - iL[idL]) / 2)
            dv_total = dv_h + dv_p + 500
            m_l = math.exp(-dv_total / (311 * 9.80665)) * 5000 - 500
            scores.append((m_l, idE))
        scores.sort(reverse=True)
        for _, idE in scores[:K]:
            pairs.add((idE, idL))
    pairs = list(pairs)
    print(f"Pairs: {len(pairs)} (~{len(pairs) * 192 * 0.3 / n_workers / 60:.0f} min est)",
           flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=3):
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
    print(f"\nTier 1A v2 done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    main(n_workers=nw, K=K)
