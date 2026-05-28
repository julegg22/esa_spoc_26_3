"""CMA-ES per-pair refinement on bank's bottom transfers.

Diagnosis: grid search has systematically missed sweet spots (the +23k
kg polish gain came from extending one grid axis). CMA-ES samples the
9-D continuous space adaptively, converging on local optima the grid
misses.

Targets: bank's bottom 200 transfers by mass (the ones with most
headroom). For each:
  - 9 free continuous vars: raan_e, argp_e, ea_dep, t0, raan_l, argp_l,
    ea_arr, t2_d, t_max_d
  - Seeded from CURRENT bank config + perturbation
  - 15 generations × population 12 = 180 evals/pair
  - pygmo CMA-ES with force_bounds=True

Per-pair wall: ~3-5 min. 200 pairs / 8 workers = ~75 min total.
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
from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


class PairOpt:
    """9-D pygmo UDP for one (idE, idL) pair."""

    def __init__(self, idE, idL):
        self.idE = idE
        self.idL = idL

    def fitness(self, x):
        udp = _UDP[0]
        raan_e, argp_e, ea_dep, t0, raan_l, argp_l, ea_arr, t2_d, t_max_d = x
        res = try_bcp_apogee_3impulse(
            udp, self.idE, self.idL,
            raan_e, argp_e, ea_dep, t0,
            raan_l, argp_l, ea_arr,
            t2_d=t2_d, t_max_d=t_max_d)
        if res is None:
            return [0.0]
        # Maximize mass = minimize -mass
        return [-res[0]]

    def get_bounds(self):
        TWO_PI = 2 * math.pi
        return ([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 10.0],
                [TWO_PI, TWO_PI, TWO_PI, TWO_PI, TWO_PI, TWO_PI, TWO_PI, 8.0, 40.0])


def _task(args):
    idx, current_row, current_mass, seed_x = args
    udp = _UDP[0]
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])

    prob = pg.problem(PairOpt(idE, idL))
    # CMA-ES with pop 12, 15 generations = 180 evals
    algo = pg.algorithm(pg.cmaes(gen=15, force_bounds=True, ftol=1e-3))

    # Seed: bank config + random small perturbation for diversity
    pop = pg.population(prob, size=0)
    rng = np.random.default_rng(idE * 1000 + idL)
    # Add seed (clamped to bounds)
    lb, ub = prob.get_bounds()
    seed_clamp = np.clip(seed_x, lb, ub)
    pop.push_back(seed_clamp)
    # Add 11 perturbations around seed
    for _ in range(11):
        perturb = rng.normal(0, 0.3, size=9)
        x = seed_clamp + perturb * (np.array(ub) - np.array(lb))
        x = np.clip(x, lb, ub)
        pop.push_back(x)

    try:
        pop = algo.evolve(pop)
    except Exception:
        return idx, None, current_mass, current_row

    best_x = pop.champion_x
    best_f = pop.champion_f[0]
    new_mass = -best_f

    if new_mass <= current_mass:
        return idx, None, current_mass, current_row

    # Re-construct the row from best_x and verify
    raan_e, argp_e, ea_dep, t0, raan_l, argp_l, ea_arr, t2_d, t_max_d = best_x
    res = try_bcp_apogee_3impulse(
        udp, idE, idL, raan_e, argp_e, ea_dep, t0,
        raan_l, argp_l, ea_arr, t2_d=t2_d, t_max_d=t_max_d)
    if res is None:
        return idx, None, current_mass, current_row
    mass_check, row, _ = res
    new_row = list(row)
    new_row[2] = idD  # keep existing idD
    chr_p = list(new_row)
    pad = (udp.dim - len(chr_p)) // 21
    for _ in range(pad):
        chr_p.extend([-1.0] + [0.0] * 20)
    actual_mass = -udp.fitness(chr_p)[0]
    if actual_mass > current_mass + 0.5:
        return idx, new_row, actual_mass, current_row
    return idx, None, current_mass, current_row


def evaluate_row(row, udp):
    chr_p = list(row)
    pad = (udp.dim - len(chr_p)) // 21
    for _ in range(pad):
        chr_p.extend([-1.0] + [0.0] * 20)
    return -udp.fitness(chr_p)[0]


def main(n_workers=8, n_targets=200):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    bank = json.load(open(bank_path))
    dv = bank[0]["decisionVector"]
    active = []
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            row = list(dv[i:i + 21])
            m = evaluate_row(row, udp)
            active.append((i // 21, row, m))
    # Sort by mass ascending; pick bottom n_targets
    active.sort(key=lambda x: x[2])
    targets = active[:n_targets]
    print(f"Bank: {len(active)} transfers, refining bottom {len(targets)} "
          f"(masses {targets[0][2]:.0f}–{targets[-1][2]:.0f} kg)",
          flush=True)

    # Build seed_x for each target from its current row config
    # We don't have the original raan_e etc. directly; use sensible defaults
    # (the actual pv0 is in row[4:10] but reconstructing exact orbital elements
    # would be expensive; just use seed=0 for everything and let CMA-ES explore)
    tasks = []
    for idx, row, m in targets:
        # Default seed: middle of parameter ranges
        seed_x = np.array([math.pi, math.pi/2, math.pi, math.pi/2,
                            math.pi/4, math.pi/4, math.pi, 1.5, 20.0])
        tasks.append((idx, row, m, seed_x))

    baseline = -udp.fitness(dv)[0]
    t_start = time.time()
    polished = list(dv)
    n_imp = 0
    total_gain = 0.0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_row in p.imap_unordered(
                _task, tasks, chunksize=1):
            orig_mass = evaluate_row(orig_row, udp)
            if new_row is None:
                continue
            gain = new_mass - orig_mass
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                n_imp += 1
                total_gain += gain
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg "
                      f"(+{gain:.0f})", flush=True)
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
    n_targets = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    main(n_workers=nw, n_targets=n_targets)
