"""Phase 2 — full pair expansion with B6 fix (post-2026-05-29).

The B6 bug fix unlocks t0 ∈ {π, 3π/2} configs that previously gave
impactor trajectories (silent reject). All historical results files
were generated with the buggy solver, so t0≠0 results in those files
were either bad or missing.

This script re-evaluates the top-K pairs per idE WITH B6 fix and
4-value t0 grid (covering the unlocked t0=π, 3π/2 region).

Per-pair grid: 3 raan × 2 ea_dep × 4 t0 × 2 ea_arr × 2 t2_d = 96 ICs.
For 400 idEs × K=10 = 4000 pairs: ~96 × 0.3 sec / 8 workers per pair ≈
3.6 sec wall per pair. 4000 pairs / 8 workers × 3.6 sec = 1800 sec
per worker → total wall ~30 min if all workers stay busy.
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

MU_MOON = 4.9028e12
ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
R_MOON_SI = 384400e3
ISP_G0 = 311.0 * 9.80665
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def score(aE, iE, aL, eL, iL):
    """Physics estimate of m_l for ranking (top-K idL per idE)."""
    r0 = aE
    r_apo_l = aL * (1.0 + eL)
    a_t = 0.5 * (r0 + R_MOON_SI)
    v0_circ = math.sqrt(MU_EARTH / r0)
    v_peri = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
    dv0 = v_peri - v0_circ
    v_target_apo = math.sqrt(MU_MOON * (1.0 - eL) / r_apo_l)
    dv_plane = 2 * v_target_apo * math.sin(abs(iE - iL) / 2)
    dv_total = dv0 + dv_plane + 500
    if dv_total > 15000:
        return 0.0
    return max(0.0, math.exp(-dv_total / ISP_G0) * 5000 - 500)


def _task(args):
    """96-IC grid covering t0 ∈ {0, π/2, π, 3π/2} (the B6-unblocked space)."""
    idE, idL = args
    udp = _UDP[0]
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 3, endpoint=False):
        for ea_dep in (0.0, np.pi):
            for t0_val in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                for ea_arr in (0.0, np.pi):
                    for t2_d in (1.5, 3.0):
                        res = try_bcp_apogee_3impulse(
                            udp, idE, idL, raan_e, 0.0, ea_dep,
                            t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                        if res is not None and (best is None or res[0] > best[0]):
                            best = res
    return idE, idL, best


def main(K=10, n_workers=8,
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/phase2_b6fix_results.json"):
    udp = LtlTrajectory(ROOT)
    aE = udp.earth_data[:, 0]
    iE = udp.earth_data[:, 2]
    aL = udp.moon_data[:, 0]
    eL = udp.moon_data[:, 1]
    iL = udp.moon_data[:, 2]

    # Per-idE top-K idL by physics estimate
    pairs = []
    for ie in range(400):
        scores = [(score(aE[ie], iE[ie], aL[il], eL[il], iL[il]), il)
                   for il in range(400)]
        scores.sort(reverse=True)
        for _, il in scores[:K]:
            pairs.append((ie, il))
    print(f"Pairs to evaluate: {len(pairs)} (400 idE × K={K})", flush=True)
    print(f"96 ICs/pair × 0.3 sec / {n_workers} workers ≈ "
          f"{len(pairs) * 96 * 0.3 / n_workers / 60:.0f} min est", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=5):
            n_done += 1
            if best is not None and best[0] > 50:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 100 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:5]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:5d}/{len(pairs)}] valid={n_valid} "
                      f"top5=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 500 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_path).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    print(f"\nPhase 2 done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K=K, n_workers=nw)
