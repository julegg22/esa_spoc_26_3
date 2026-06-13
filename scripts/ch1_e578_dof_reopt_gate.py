"""E-578 — GATE: are the 301 FILLED bank pairs at per-pair DoF-optimal mass?

Task lever (distinct from E-047 which studied raan for FILLING empty slots):
hold the (idE,idL) ASSIGNMENT fixed for already-filled pairs and re-maximize
mass over the free DoF (raan_e, argp_e, ea_dep, ea_arr, t0, t2_d) with the
FAITHFUL apogee solver. Compare new mass vs banked per-pair mass.

Prior work (git log): ch1_apogee_polish.py drove +23k kg (May 26), and
polish_to_theoretical (pygmo SADE 12-DoF on the 176 pairs with >200kg
theoretical gap) found only +14 kg (1/176) on May 30 -> strong prior that
the bank is at per-pair optimum. This gate independently re-checks 12 pairs
spanning the inclination range with a faithful, finer apogee sweep.

Read-only: prints deltas only. 2 workers.
"""
from __future__ import annotations
import json, sys, time
from multiprocessing import Pool
import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory  # noqa: E402
from esa_spoc_26.ch1_apogee_plane_change import try_apogee_plane_change  # noqa

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"

# sweep grids (finer than apogee_polish.py's 4x3x4x2x4x3=576; here ~1536)
RAAN_E = list(np.linspace(0, 2 * np.pi, 8, endpoint=False))
ARGP_E = list(np.linspace(0, 2 * np.pi, 4, endpoint=False))
EA_DEP = list(np.linspace(0, 2 * np.pi, 8, endpoint=False))
EA_ARR = (0.0, np.pi / 2, np.pi, 3 * np.pi / 2)
T0_GRID = (0.0, np.pi)
T2_GRID = (1.0, 1.5, 2.0, 3.0)
WALL = 480.0  # s per pair


def eval_row(udp, row):
    chr_ = list(row)
    pad = (udp.dim - len(chr_)) // 21
    for _ in range(pad):
        chr_.extend([-1.0] + [0.0] * 20)
    return -udp.fitness(chr_)[0]


def reopt_pair(args):
    idE, idL, banked_mass = args
    udp = LtlTrajectory(DD)
    t0 = time.time()
    best = None
    n = 0
    for raan_e in RAAN_E:
        for argp_e in ARGP_E:
            for ea_dep in EA_DEP:
                for t0v in T0_GRID:
                    for ea_arr in EA_ARR:
                        for t2_d in T2_GRID:
                            n += 1
                            res = try_apogee_plane_change(
                                udp, idE, idL, raan_e, argp_e, ea_dep,
                                0.0, 0.0, ea_arr, t0v, t2_d)
                            if res is not None and (best is None or res[0] > best):
                                best = res[0]
                            if time.time() - t0 > WALL:
                                return idE, idL, banked_mass, best, n, time.time() - t0
    return idE, idL, banked_mass, best, n, time.time() - t0


def main():
    udp = LtlTrajectory(DD)
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    filled = [(i, rows[i]) for i in range(len(rows)) if rows[i][0] >= 0]
    iE = np.array([np.degrees(udp.earth_data[int(r[0]), 2]) for _, r in filled])
    order = np.argsort(iE)
    # 12 pairs spanning low/mid/high inclination
    pick_idx = np.linspace(0, len(order) - 1, 12).astype(int)
    sample = []
    for pi in pick_idx:
        i, r = filled[order[pi]]
        m = eval_row(udp, r)
        sample.append((int(r[0]), int(r[1]), m, float(iE[order[pi]])))
    print("[E-578] 12-pair DoF re-opt GATE on FILLED bank pairs", flush=True)
    print(f"  bank total mass = {-udp.fitness(b)[0]:.1f} kg (301 filled)", flush=True)
    for idE, idL, m, i in sample:
        print(f"  pick E{idE}->L{idL} iE={i:.1f} banked={m:.1f}kg", flush=True)
    print("  re-solving (faithful apogee, ~1536 sweep/pair)...", flush=True)

    t0 = time.time()
    with Pool(2) as p:
        res = p.map(reopt_pair, [(e, l, m) for e, l, m, _ in sample])

    print("=" * 70, flush=True)
    tot_bank = 0.0
    tot_new = 0.0
    for (idE, idL, bm), (re, rl, rbm, new, n, dt) in zip(
            [(e, l, m) for e, l, m, _ in sample], res):
        newm = -1.0 if new is None else new
        delta = (newm - bm) if new is not None else float("nan")
        tot_bank += bm
        tot_new += max(newm, bm)  # keep-best-of (re-opt never loses)
        tag = ""
        if new is None:
            tag = "  re-opt FAILED (no valid)"
        elif delta > 1.0:
            tag = f"  <<< GAIN +{delta:.1f}"
        elif delta < -1.0:
            tag = "  (re-opt below bank -> bank better, keep bank)"
        print(f"E{idE}->L{idL}: banked={bm:.1f} reopt={'FAIL' if new is None else f'{newm:.1f}'}"
              f" delta={delta:+.1f}kg [{n} tries,{dt:.0f}s]{tag}", flush=True)
    print("=" * 70, flush=True)
    samp_gain = tot_new - tot_bank
    pct = 100 * samp_gain / tot_bank if tot_bank else 0
    extrap = samp_gain / 12 * 301
    print(f"SAMPLE: bank={tot_bank:.1f}kg  keep-best={tot_new:.1f}kg  "
          f"gain=+{samp_gain:.1f}kg ({pct:.3f}%)", flush=True)
    print(f"EXTRAPOLATED to 301 filled: +{extrap:.0f} kg "
          f"(bank 236420 -> {236420 + extrap:.0f})", flush=True)
    verdict = "PROCEED (gate passes, >2% or large pair gains)" if pct > 2.0 else \
        "STOP — bank is per-pair DoF-optimal, mass lever exhausted on filled pairs"
    print(f"VERDICT: {verdict}", flush=True)
    print(f"[total {time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
