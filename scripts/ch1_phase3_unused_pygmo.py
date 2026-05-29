"""Phase 3 — pygmo SADE on the 104 UNUSED (idE, idL) pairs (L3 lever).

Per the coherent model (A-2026-05-29), the bank has 104 unused idEs and
104 unused idLs. Cracking these via Hungarian re-bank could add +50-90k kg.
The bottleneck has been: per-pair grid search misses good local optima.

This script applies pygmo SADE (self-adaptive DE) per unused-idE × top-K
idL by physics estimate. Each pygmo call: 30 pop × 60 gen = 1800 evals,
~70 sec wall on 1 core. 104 idE × 20 idL = 2080 pairs / 8 workers ~ 5h.

Save results → Hungarian rebank with combined pool.
"""
import sys
import time
import json
import math
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

import pygmo as pg
from esa_spoc_26.ch1_pair_udp import (
    PairUDP, multi_seed_pop, chromosome_to_row, mass_from_row,
    M0, M_DRY, ISP_G0,
)
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, MU_EARTH

MU_MOON = 4.9028e12
ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
R_MOON_SI = 384400e3
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def physics_estimate(aE, iE, aL, eL, iL):
    """m_l estimate for pair ranking."""
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
    return max(0.0, math.exp(-dv_total / ISP_G0) * M0 - M_DRY)


def _task(args):
    """Run pygmo SADE on one (idE, idL) pair. Returns (idE, idL, best_or_None)."""
    idE, idL = args
    udp = _UDP[0]
    prob = pg.problem(PairUDP(udp, idE, idL))
    algo = pg.algorithm(pg.sade(gen=60, ftol=0.0, xtol=0.0))
    # Multi-seed without bank row (unused pair)
    pop = multi_seed_pop(prob, udp, idE, idL, pop_size=30, bank_row=None)
    try:
        pop = algo.evolve(pop)
    except Exception:
        return idE, idL, None
    best_dv = pop.champion_f[0]
    best_x = pop.champion_x
    if best_dv > 1e5:
        return idE, idL, None
    row = chromosome_to_row(udp, best_x, idE, idL)
    if row is None:
        return idE, idL, None
    mass = mass_from_row(udp, row)
    if mass < 50:
        return idE, idL, None
    return idE, idL, (mass, row, best_dv)


def main(K=20, n_workers=8,
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/phase3_pygmo_results.json"):
    udp = LtlTrajectory(ROOT)
    aE_arr = udp.earth_data[:, 0]
    iE_arr = udp.earth_data[:, 2]
    aL_arr = udp.moon_data[:, 0]
    eL_arr = udp.moon_data[:, 1]
    iL_arr = udp.moon_data[:, 2]

    # Find unused (idE, idL)
    bank = json.load(open("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json"))
    dv = bank[0]["decisionVector"]
    used_e = set()
    used_l = set()
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            used_e.add(int(dv[i]))
            used_l.add(int(dv[i + 1]))
    unused_e = [e for e in range(400) if e not in used_e]
    unused_l = [l for l in range(400) if l not in used_l]
    print(f"Unused: {len(unused_e)} idE, {len(unused_l)} idL", flush=True)

    # Per unused idE, top-K unused idL by physics estimate
    pairs = []
    for ie in unused_e:
        scores = [(physics_estimate(aE_arr[ie], iE_arr[ie],
                                      aL_arr[il], eL_arr[il], iL_arr[il]), il)
                   for il in unused_l]
        scores.sort(reverse=True)
        for _, il in scores[:K]:
            pairs.append((ie, il))
    print(f"Pairs to evaluate via pygmo SADE: {len(pairs)}", flush=True)
    print(f"Est wall: ~{len(pairs) * 70 / n_workers / 60:.0f} min", flush=True)

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
    print(f"\nPhase 3 done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K=K, n_workers=nw)
