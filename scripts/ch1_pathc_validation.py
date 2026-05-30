"""Path C validation: can a heavy-budget pygmo NLP reach theoretical
impulsive max on 5 test pairs?

The 'polish-to-theoretical' experiment used pygmo SADE with 80 gen × 30
pop = 2,400 evals per pair, found only +14 kg total. This validation
goes much heavier:
  - CMA-ES with 150 gen × 50 pop = 7,500 evals per RESTART
  - 5 random restarts per pair = 37,500 evals per pair
  - Smart seeding: fine-grid pre-search + best-bank seed if available

If actual ≥ 90% of theoretical for at least 3 of 5 test pairs → impulsive
PathA is reachable, commit 1-2 wks to full multi-shoot DC implementation.

If actual < 50% of theoretical on ALL 5 → architecture is the limit,
PathB pivot (submit current bank, focus on Ch2/Ch3).

Test pairs:
  (8, 175)   — bank 951, theory 1085 (LEO+high-eL, moderate plane change)
  (38, 157)  — bank 841, theory ~950 (LEO+high-eL, slightly bigger plane)
  (260, 193) — bank 1407, theory 2214 (already-good high-aE+high-eL)
  (227, 315) — bank 27, theory 985 (LMO target, near-coplanar, big gap)
  (291, 224) — bank 506, theory 1792 (mid-eL with biggest gap from polish)
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

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
MU_MOON = 4.9028e12
R_MOON_SI = 384400e3


def theoretical_m_l(aE, iE, aL, eL, iL):
    """Per-pair impulsive theoretical max (apoapsis arrival)."""
    r0 = aE; r_apo = aL * (1.0 + eL)
    a_t = (r0 + R_MOON_SI) / 2.0
    v0 = math.sqrt(MU_EARTH / r0)
    v_peri = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
    dv0 = v_peri - v0
    v_apo_E = math.sqrt(MU_EARTH * (2.0 / R_MOON_SI - 1.0 / a_t))
    v_moon = math.sqrt(MU_EARTH / R_MOON_SI)
    v_inf = abs(v_apo_E - v_moon)
    v_perilune = math.sqrt(v_inf ** 2 + 2.0 * MU_MOON / r_apo)
    v_target_apo = math.sqrt(MU_MOON * (1.0 - eL) / r_apo)
    angle = abs(iE - iL)
    dv2 = math.sqrt(v_perilune ** 2 + v_target_apo ** 2
                     - 2.0 * v_perilune * v_target_apo * math.cos(angle))
    return math.exp(-(dv0 + dv2) / ISP_G0) * M0 - M_DRY


def heavy_nlp(udp, idE, idL, bank_row=None, n_restarts=5):
    """5 random-restart CMA-ES rounds, return best mass."""
    prob = pg.problem(PairUDP(udp, idE, idL))
    best_mass = 0.0
    best_row = None

    for r in range(n_restarts):
        # Each restart: pop=40, gen=120 = 4800 evals
        algo = pg.algorithm(pg.cmaes(gen=120, force_bounds=True, ftol=0.0))
        # Seed: bank row (if any) + multi-phasing Hohmann + random
        rng = np.random.default_rng(idE * 1000 + idL + r * 12345)
        pop = multi_seed_pop(prob, udp, idE, idL, pop_size=40,
                              bank_row=bank_row if r == 0 else None,
                              rng=rng)
        try:
            pop = algo.evolve(pop)
        except Exception:
            continue
        if pop.champion_f[0] > 1e5:
            continue
        row = chromosome_to_row(udp, pop.champion_x, idE, idL)
        if row is None:
            continue
        m = mass_from_row(udp, row)
        if m > best_mass:
            best_mass = m
            best_row = row
    return best_mass, best_row


def _task(args):
    idE, idL, bank_row = args
    udp = LtlTrajectory(ROOT)
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    theory = theoretical_m_l(aE, iE, aL, eL, iL)
    bank_m = mass_from_row(udp, bank_row) if bank_row else 0.0

    t_start = time.time()
    best_m, best_row = heavy_nlp(udp, idE, idL, bank_row=bank_row)
    elapsed = time.time() - t_start

    return idE, idL, bank_m, best_m, theory, elapsed


def main(n_workers=8):
    udp = LtlTrajectory(ROOT)
    bank = json.load(open("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json"))
    dv = bank[0]["decisionVector"]
    bank_rows = {}
    for i in range(0, len(dv), 21):
        if dv[i] < 0:
            continue
        bank_rows[(int(dv[i]), int(dv[i + 1]))] = list(dv[i:i + 21])

    test_pairs = [
        (8, 175),
        (38, 157),
        (260, 193),
        (227, 315),
        (291, 224),
    ]
    tasks = [(ie, il, bank_rows.get((ie, il))) for ie, il in test_pairs]

    print(f"PATH C VALIDATION: heavy NLP (5 restarts × 4800 evals = 24k/pair)",
           flush=True)
    print(f"Test pairs: {test_pairs}", flush=True)
    print(f"Expected wall: ~30-60 min on {n_workers} workers\n", flush=True)

    t_start = time.time()
    n_pass = 0
    results = []
    with mp.Pool(n_workers) as p:
        for idE, idL, bank_m, best_m, theory, elapsed in p.imap_unordered(
                _task, tasks):
            results.append((idE, idL, bank_m, best_m, theory, elapsed))
            frac = (best_m / theory) * 100 if theory > 0 else 0
            verdict = "PASS (≥90% theory)" if frac >= 90 else \
                       "MID (50-90%)" if frac >= 50 else \
                       "FAIL (<50%)"
            print(f"  ({idE:3d}, {idL:3d}) bank={bank_m:.0f} → "
                  f"heavy_nlp={best_m:.0f} | theory={theory:.0f} | "
                  f"{frac:.0f}% — {verdict}  [{elapsed:.0f}s]", flush=True)
            if frac >= 90:
                n_pass += 1

    print(f"\nTotal wall: {time.time() - t_start:.0f}s", flush=True)
    print(f"PATH C VERDICT: {n_pass}/5 reached ≥90% of theoretical", flush=True)
    if n_pass >= 3:
        print("  → PATH A (multi-shoot DC) is REACHABLE; commit to 1-2 wk impl",
               flush=True)
    elif n_pass >= 1:
        print("  → MIXED signal; per-pair physics determines whether multi-shoot helps",
               flush=True)
    else:
        print("  → PATH B PIVOT: impulsive architecture truly capped; "
              "submit Ch1 and focus Ch2/Ch3", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=nw)
