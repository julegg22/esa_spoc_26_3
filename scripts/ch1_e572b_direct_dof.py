"""E-572b — corrected multi-DoF feasibility test using the PROVEN solver.

E-572 (6-D DC, split=0.5, try_transfer) was confounded: it FAILS even on
KNOWN-banked-feasible pairs (E0->L0, banked 819kg). The bank's rows are
single-burn-to-LOI (T2=0, split->1.0), produced by solve_transfer_direct /
solve_transfer_dc in ch1_trajectory_solve.py, NOT the split=0.5 6-D DC. So
E-572's REFUTED verdict only proves that *architecture* fails, not that the
free DoF don't help.

This test uses solve_transfer_direct, which already accepts (raan, argp) for
the EARTH orbit, is fast (~11s/call), and is one of the engines that built
the bank. For each moderate-incl stranded pair we compare:
  BASELINE  : raan=argp=0  (16 departure phases, t0=0)
  DoF SWEEP : grid over earth raan x argp  (same phasing)
A FAIL->feasible flip on any pair = the RAAN/argp lead is confirmed.

solve_transfer_direct returns (row, mass, dv_ms, dt_d, err) when valid, else
(None, best_closest_approach_err_m). We record the err so "FAIL" cases are
quantified (near-miss vs hopeless).
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")

from esa_spoc_26.ch1_trajectory import LtlTrajectory  # noqa: E402
from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct  # noqa: E402

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def best_over(udp, idE, idL, orients, n_phase, t0_grid):
    """Best feasible mass and min closest-approach err over an orientation
    and t0 grid. Returns (best_mass_or_None, min_err_m)."""
    best, min_err = None, np.inf
    for (raan, argp) in orients:
        for t0 in t0_grid:
            r = solve_transfer_direct(udp, idE, idL, n_phase=n_phase,
                                      t0=t0, raan=raan, argp=argp)
            if r[0] is not None:
                m = r[1]
                if best is None or m > best:
                    best = m
            else:
                min_err = min(min_err, r[1])
    return best, min_err


def eval_pair(args):
    idE, idL = args
    udp = LtlTrajectory(DD)
    iE = float(np.degrees(udp.earth_data[idE, 2]))
    iL = float(np.degrees(udp.moon_data[idL, 2]))
    t0 = time.time()

    t0_grid = (0.0, np.pi)

    # BASELINE: raan=argp=0
    base, base_err = best_over(udp, idE, idL, [(0.0, 0.0)],
                               n_phase=24, t0_grid=t0_grid)

    # DoF SWEEP: earth raan x argp grid (fewer phases/orient to bound cost)
    raan_g = np.linspace(0, 2 * np.pi, 4, endpoint=False)
    argp_g = [0.0, np.pi / 2, np.pi, 3 * np.pi / 2]
    orients = [(r, a) for r in raan_g for a in argp_g]
    swp, swp_err = best_over(udp, idE, idL, orients,
                             n_phase=12, t0_grid=t0_grid)

    return dict(idE=idE, idL=idL, iE=iE, iL=iL, base=base,
                base_err=base_err, swp=swp, swp_err=swp_err,
                t=time.time() - t0)


def main():
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    udp = LtlTrajectory(DD)
    earth, moon = udp.earth_data, udp.moon_data
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0][
        "decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    usedE = set(int(r[0]) for r in rows if r[0] >= 0)
    usedL = set(int(r[1]) for r in rows if r[0] >= 0)
    unusedE = [k for k in range(len(earth)) if k not in usedE]
    unusedL = [k for k in range(len(moon)) if k not in usedL]
    iE = np.degrees(earth[:, 2])

    mod = sorted([k for k in unusedE if 60 <= iE[k] <= 78],
                 key=lambda k: iE[k])
    if len(mod) > 8:
        idx = np.linspace(0, len(mod) - 1, 8).astype(int)
        mod = [mod[i] for i in idx]
    pairs = []
    for idEk in mod:
        idLk = min(unusedL, key=lambda k: abs(moon[k, 2] - earth[idEk, 2]))
        pairs.append((idEk, idLk))

    # POSITIVE CONTROL: a few low-incl pairs (one used) to prove the engine
    # can produce feasibility at all on this dataset.
    ctrl = []
    low_used = sorted([k for k in usedE], key=lambda k: iE[k])[:2]
    for idEk in low_used:
        idLk = int([r[1] for r in rows if int(r[0]) == idEk][0])
        ctrl.append((idEk, idLk))

    print(f"[E-572b] {len(ctrl)} control + {len(pairs)} moderate-incl pairs",
          flush=True)
    print("control:", ctrl, "moderate:", pairs, flush=True)

    t_all = time.time()
    with Pool(2) as p:
        ctrl_res = p.map(eval_pair, ctrl)
        results = p.map(eval_pair, pairs)

    print("\n--- POSITIVE CONTROL (low-incl, should be feasible) ---",
          flush=True)
    for r in ctrl_res:
        base = "FAIL" if r["base"] is None else f"{r['base']:.0f}kg"
        swp = "FAIL" if r["swp"] is None else f"{r['swp']:.0f}kg"
        print(f"E{r['idE']}(i={r['iE']:.1f}) L{r['idL']}: base={base} "
              f"(err{r['base_err']:.0f}m) sweep={swp} [{r['t']:.0f}s]",
              flush=True)

    print("\n--- MODERATE-INCL STRANDED PAIRS ---", flush=True)
    n_unlock = 0
    for r in results:
        base = "FAIL" if r["base"] is None else f"{r['base']:.0f}kg"
        swp = "FAIL" if r["swp"] is None else f"{r['swp']:.0f}kg"
        tag = ""
        if r["base"] is None and r["swp"] is not None:
            tag = "  <<< UNLOCKED"
            n_unlock += 1
        print(f"E{r['idE']}(i={r['iE']:.1f}) L{r['idL']}(i={r['iL']:.1f}): "
              f"base={base}(err{r['base_err']:.0f}m) "
              f"sweep={swp}(err{r['swp_err']:.0f}m) [{r['t']:.0f}s]{tag}",
              flush=True)

    ctrl_ok = any(r["base"] is not None or r["swp"] is not None
                  for r in ctrl_res)
    print("\n" + "=" * 60, flush=True)
    if not ctrl_ok:
        print("[CAUTION] positive control also FAILED -> engine/phasing too "
              "coarse to certify; treat moderate-incl result as inconclusive.",
              flush=True)
    if n_unlock > 0:
        print(f"[VERDICT] CONFIRMED: {n_unlock}/{len(pairs)} unlocked by "
              f"earth RAAN/argp DoF.", flush=True)
    else:
        print(f"[VERDICT] No unlock: 0/{len(pairs)} "
              f"(control_ok={ctrl_ok}).", flush=True)
    print(f"[total wall {time.time()-t_all:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
