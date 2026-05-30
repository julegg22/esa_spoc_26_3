"""Polish bank transfers toward their per-pair theoretical impulsive ceiling.

The per-instance check (2026-05-30) showed 257 of 302 bank transfers are
>50 kg below their theoretical max. Top gaps: 1286 kg, 959, 841, 831...
Total headroom: ~96k kg (vs +60k WSB estimate).

For each (idE, idL) with gap > 200 kg, run pygmo SADE on the 12-dof
problem (PairUDP). Replace bank entry if better.

Per-pair: ~3-5 min wall. 257 pairs / 8 workers = ~2 hours. Big potential.
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
)
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
MU_EARTH = 398600435507000.0
MU_MOON = 4.9028e12
R_MOON_SI = 384400e3
ISP_G0 = 311.0 * 9.80665
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def theoretical_m_l(aE, iE, aL, eL, iL):
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
    return math.exp(-(dv0 + dv2) / ISP_G0) * 5000.0 - 500.0


def _task(args):
    idx, bank_row, current_mass, theoretical = args
    udp = _UDP[0]
    idE = int(bank_row[0])
    idL = int(bank_row[1])
    idD = int(bank_row[2])

    prob = pg.problem(PairUDP(udp, idE, idL))
    # SADE for global; CMA-ES would also work
    algo = pg.algorithm(pg.sade(gen=80, ftol=0.0, xtol=0.0))
    pop = multi_seed_pop(prob, udp, idE, idL, pop_size=30,
                          bank_row=bank_row)
    try:
        pop = algo.evolve(pop)
    except Exception:
        return idx, None, current_mass, theoretical
    best_dv = pop.champion_f[0]
    best_x = pop.champion_x
    if best_dv > 1e5:
        return idx, None, current_mass, theoretical
    row = chromosome_to_row(udp, best_x, idE, idL, idD=idD)
    if row is None:
        return idx, None, current_mass, theoretical
    actual_m = mass_from_row(udp, row)
    if actual_m > current_mass + 5:
        return idx, row, actual_m, theoretical
    return idx, None, current_mass, theoretical


def main(n_workers=8, min_gap=200):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    bank = json.load(open(bank_path))
    dv = bank[0]["decisionVector"]

    # Build polish targets: pairs with gap > min_gap
    targets = []
    for i in range(0, len(dv), 21):
        if dv[i] < 0:
            continue
        row = list(dv[i:i + 21])
        idE = int(row[0]); idL = int(row[1])
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        chr_p = list(row) + [-1.0] * 20 * (400 - 1)
        chr_p = chr_p[:udp.dim]
        m_actual = -udp.fitness(chr_p)[0]
        m_theory = theoretical_m_l(aE, iE, aL, eL, iL)
        gap = m_theory - m_actual
        if gap > min_gap:
            targets.append((i // 21, row, m_actual, m_theory))

    print(f"Bank: 302 transfers; {len(targets)} have gap > {min_gap} kg",
           flush=True)
    targets.sort(key=lambda t: -(t[3] - t[2]))
    total_gap = sum(t[3] - t[2] for t in targets)
    print(f"Total addressable headroom: {total_gap:.0f} kg", flush=True)
    print(f"Est per-pair ~4 min wall × {len(targets)} / {n_workers} workers = "
          f"{len(targets) * 4 / n_workers:.0f} min", flush=True)

    baseline = -udp.fitness(dv)[0]
    t_start = time.time()
    polished = list(dv)
    n_imp = 0
    total_gain = 0.0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, theory in p.imap_unordered(
                _task, targets, chunksize=1):
            if new_row is None:
                continue
            offset = idx * 21
            old_chr = polished[offset:offset + 21] + [-1.0] * 20 * 399
            old_chr = old_chr[:udp.dim]
            old_mass = -udp.fitness(old_chr)[0]
            gain = new_mass - old_mass
            if gain > 0.5:
                polished[offset:offset + 21] = list(new_row)
                n_imp += 1
                total_gain += gain
                frac = (new_mass / theory) * 100
                print(f"  [{idx:3d}] {old_mass:.0f} → {new_mass:.0f} "
                      f"(+{gain:.0f}, {frac:.0f}% of theory {theory:.0f})",
                      flush=True)
                if n_imp % 5 == 0:
                    bank_path.write_text(json.dumps([{
                        "decisionVector": [float(v) for v in polished],
                        "problem": "trajectory",
                        "challenge": "spoc-4-luna-tomato-logistics"}]))
    f_p = -udp.fitness(polished)[0]
    print(f"\n{n_imp}/{len(targets)} improved, +{total_gain:.0f}kg "
          f"in {time.time() - t_start:.0f}s", flush=True)
    if f_p > baseline + 0.5:
        bank_path.write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics"}]))
        print(f"BANKED: {baseline:.0f} → {f_p:.0f}kg", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    min_gap = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    main(n_workers=nw, min_gap=min_gap)
