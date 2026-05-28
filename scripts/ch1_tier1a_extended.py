"""Tier 1A — Sun-assist-friendly extended sweep (C-024 design).

Hypothesis: BCP includes Sun gravity. Long TOFs (30-60 days) with long
coast durations (5-20 days) may let Sun's perturbation bring trajectories
into high-eL Moon orbit naturally — the C-022 architecture with new
extended grid axes.

Targets: 150 high-eL Moon orbits (aL > 3M, eL > 0.4) where Sun-assist
plausibly accessible. For each, sweep:
  t_max_d ∈ {30, 45, 60} (BCP propagation window)
  t2_d ∈ {1, 3, 5, 8, 12, 20} (long-coast variants)

Per-pair: 8 raan × 4 ea_dep × 4 t0 × 3 t_max × 6 t2_d = 2304 ICs.
Targeting the top-K LEO idEs per Moon idL (K=20).

If this finds significant gain, Sun-assist IS accessible by grid
extension — and Tier 1B (energy-reduction at perilune) is the next
step. If 0 gain, manifold targeting required (Tier 2).

Run: nohup python ch1_tier1a_extended.py > runs/ch1/66_tier1a.log &
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
    """Extended grid: 8 × 4 × 4 × 3 × 6 = 2304 ICs/pair."""
    idE, idL = args
    udp = _UDP[0]
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
            for t0_val in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                for t_max_d in (30.0, 45.0, 60.0):
                    for t2_d in (1.0, 3.0, 5.0, 8.0, 12.0, 20.0):
                        res = try_bcp_apogee_3impulse(
                            udp, idE, idL, raan_e, 0.0, ea_dep,
                            t0_val, 0.0, 0.0, 0.0,
                            t2_d=t2_d, t_max_d=t_max_d)
                        if res is not None and (best is None or res[0] > best[0]):
                            best = res
    return idE, idL, best


def main(n_workers=8, K=15,
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/tier1a_results.json"):
    udp = LtlTrajectory(ROOT)
    aE = udp.earth_data[:, 0]
    iE = udp.earth_data[:, 2]
    aL = udp.moon_data[:, 0]
    eL = udp.moon_data[:, 1]
    iL = udp.moon_data[:, 2]

    # Select high-eL Moon targets (where Sun-assist might help)
    high_el = [l for l in range(400) if aL[l] > 3e6 and eL[l] > 0.4]
    print(f"High-eL Moon orbits (aL>3M, eL>0.4): {len(high_el)}", flush=True)

    # Per-idL: top-K LEO idEs by Hohmann mass estimate
    R_MOON_SI = 384400e3
    pairs = set()
    for idL in high_el:
        scores = []
        r_apo_l = aL[idL] * (1.0 + eL[idL])
        for idE in range(400):
            if aE[idE] > 1.5e7:  # only LEO/MEO
                continue
            r0 = aE[idE]
            a_t = 0.5 * (r0 + R_MOON_SI)
            v_peri = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
            v0 = math.sqrt(MU_EARTH / r0)
            dv_h = v_peri - v0
            # plane change at apolune
            v_target_apo = math.sqrt(4.9028e12 * (1.0 - eL[idL]) / r_apo_l)
            dv_p = 2 * v_target_apo * math.sin(abs(iE[idE] - iL[idL]) / 2)
            dv_total = dv_h + dv_p + 500  # LOI estimate
            m_l = math.exp(-dv_total / (311 * 9.80665)) * 5000 - 500
            scores.append((m_l, idE))
        scores.sort(reverse=True)
        for _, idE in scores[:K]:
            pairs.add((idE, idL))
    pairs = list(pairs)
    print(f"Pairs to evaluate: {len(pairs)}", flush=True)
    print(f"Per-pair: 2304 ICs. Est wall: "
          f"~{len(pairs) * 2304 * 0.3 / n_workers / 60:.0f} min", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=1):
            n_done += 1
            if best is not None and best[0] > 50:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 25 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:5]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"top5=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 100 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_path).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    print(f"\nTier 1A done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    main(n_workers=nw, K=K)
