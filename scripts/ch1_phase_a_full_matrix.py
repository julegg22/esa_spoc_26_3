"""Phase A — full-matrix candidate pool expansion (the BIG lever).

Diagnosis 2026-05-27: of 400×400 = 160,000 possible (idE, idL) pairings,
the solver has tested only ~14,000 (8.75%). Hungarian picks among what
we test — so the bank's quality is bounded by candidate-pool coverage,
not by solver quality.

This script:
1. For each (idE, idL) pair, compute a PHYSICS-BASED mass estimate
   (Hohmann + apolune plane change + LOI dv).
2. For each idE, pick top-K idL candidates by estimate.
3. Evaluate each (idE, idL) candidate not yet in our results files
   via the reduced-grid C-022 solver.
4. Save results to `runs/ch1/phase_a_results.json` for later rebank.

K=30 → 400×30 = 12,000 new pairs. With reduced grid (24 evals)
at ~3-5 sec/pair on 8 workers ≈ 75-125 min wall.

Note: this evaluates ALL idE (used AND unused), not just unused.
Hungarian can re-pair existing bank entries with newly-found idLs.
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
M0 = 5000.0
M_DRY = 500.0
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def physics_mass_estimate(aE, iE, aL, eL, iL):
    """Quick analytical mass estimate via Hohmann + apolune plane change + LOI.

    Used as the SCORING metric for picking top-K idLs per idE.
    """
    r0 = aE  # circular LEO
    r_apo_l = aL * (1.0 + eL)
    a_trans = 0.5 * (r0 + R_MOON_SI)
    v0_circ = math.sqrt(MU_EARTH / r0)
    v_peri_t = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_trans))
    dv0_hohmann = v_peri_t - v0_circ

    # Moon-frame encounter velocity (rough)
    v_apo_E = math.sqrt(MU_EARTH * (2.0 / R_MOON_SI - 1.0 / a_trans))
    v_moon_around_earth = math.sqrt(MU_EARTH / R_MOON_SI)
    v_inf = abs(v_apo_E - v_moon_around_earth)

    # Approach speed at r_apo_l from Moon (using v_inf as energy)
    v_approach_at_apo = math.sqrt(v_inf ** 2 + 2.0 * MU_MOON / r_apo_l)
    # Target velocity at apolune of Moon orbit:
    v_target_apo = math.sqrt(MU_MOON * (1.0 - eL) / r_apo_l)
    dv_loi = abs(v_approach_at_apo - v_target_apo)

    # Plane change at apolune (low velocity = cheap)
    plane_change_angle = abs(iE - iL)
    dv_plane = 2.0 * v_target_apo * math.sin(plane_change_angle / 2.0)

    dv_total = dv0_hohmann + dv_plane + dv_loi
    if dv_total > 15000:
        return 0.0
    m_l = math.exp(-dv_total / ISP_G0) * M0 - M_DRY
    return max(0.0, m_l)


def _task(args):
    """Reduced grid (24 evals) — fast screen for many pairs."""
    idE, idL = args
    udp = _UDP[0]
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
            for t0_val in (0.0, np.pi):
                for ea_arr in (0.0, np.pi):  # reduced from 4
                    for t2_d in (0.5, 1.5):
                        res = try_bcp_apogee_3impulse(
                            udp, idE, idL, raan_e, 0.0, ea_dep,
                            t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                        if res is not None and (best is None or res[0] > best[0]):
                            best = res
    return idE, idL, best


def load_already_tested():
    """Collect all (idE, idL) pairs from existing results files + bank."""
    tested = set()
    results_files = list(Path("/home/julian/Projects/esa_spoc_26_3/runs/ch1").glob(
        "bcp_apogee_expand_*results.json"))
    for f in results_files:
        try:
            d = json.load(open(f))
            for k in d.keys():
                idE, idL = map(int, k.split(','))
                tested.add((idE, idL))
        except Exception:
            pass
    # bank
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        for i in range(0, len(dv), 21):
            if dv[i] >= 0:
                tested.add((int(dv[i]), int(dv[i + 1])))
    return tested


def main(K=30, n_workers=8,
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/phase_a_results.json"):
    udp = LtlTrajectory(ROOT)
    aE = udp.earth_data[:, 0]
    iE = udp.earth_data[:, 2]
    aL = udp.moon_data[:, 0]
    eL = udp.moon_data[:, 1]
    iL = udp.moon_data[:, 2]

    print("Computing physics-based score matrix (400×400)…", flush=True)
    M = np.zeros((400, 400))
    for ie in range(400):
        for il in range(400):
            M[ie, il] = physics_mass_estimate(
                aE[ie], iE[ie], aL[il], eL[il], iL[il])

    tested = load_already_tested()
    print(f"Already tested: {len(tested)} pairs", flush=True)

    # Per-idE, take top-K idLs by score that aren't already tested
    pairs = []
    for ie in range(400):
        scores = [(M[ie, il], il) for il in range(400)]
        scores.sort(reverse=True)
        added = 0
        for _, il in scores:
            if added >= K:
                break
            if (ie, il) in tested:
                continue
            pairs.append((ie, il))
            added += 1
    print(f"Candidates to evaluate: {len(pairs)}", flush=True)
    print(f"Est wall: ~{len(pairs) * 3.5 / n_workers / 60:.0f} min", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=10):
            n_done += 1
            if best is not None and best[0] > 50:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 200 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:5]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:5d}/{len(pairs)}] valid={n_valid} "
                      f"top5=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 1000 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_path).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    wall = time.time() - t_start
    print(f"\nPhase A done in {wall:.0f}s: {n_valid}/{n_done} valid",
           flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(K=K, n_workers=nw)
