"""E-572 — Multi-DoF feasibility test for stranded MODERATE-inclination
(60-78 deg) Earth->Moon pairs in Ch1.

Lead: the official validator `_match_orbit` checks ONLY (a,e,i). RAAN/argp
of both the Earth departure and Moon arrival orbit are FREE, and the burn
`split` (T1/T2 fraction) is hardcoded 0.5 in every solver. E-571 swept only
earth RAAN on 3 near-90deg orbits (a weak test) and found no unlock.

This test, on a REPRESENTATIVE sample of moderate-incl stranded pairs:
  BASELINE : raan_e=argp_e=raan_l=argp_l=0, split=0.5, swept over tof x ea
  MULTI-DoF: coarse grid over raan_e, argp_e, argp_l, split, tof, ea

A FAIL(baseline) -> FEASIBLE(sweep) flip on even one pair = lead confirmed.

Speed: try_transfer's 6-D DC propagates the BCP per nfev (~8.6s/call at
max_nfev=100). We (a) cap max_nfev to make calls cheap, (b) add a cheap
Lambert |dv0| prefilter (already in try_transfer, but we also reject high
relative-plane geometries early), (c) parallelize across pairs with 2
workers. We replicate try_transfer's body so `split` becomes a free knob.
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

from esa_spoc_26.ch1_trajectory import (  # noqa: E402
    T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0  # noqa: E402
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
MAX_NFEV = 40  # capped DC budget for speed (vs 100 in try_transfer)


def try_transfer_split(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                       split, idE, idL, max_nfev=MAX_NFEV):
    """try_transfer (6-D DC) with a FREE burn `split` and capped nfev.
    Returns (mass, dv_ms) or None."""
    dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
        return None
    if np.linalg.norm(dv0_seed) > 15:
        return None
    T1 = split * tof
    T2 = (1 - split) * tof

    def residual(p):
        dv0 = p[:3].tolist()
        dv1 = p[3:6].tolist()
        pv_a = propagate(pv0, 0.0, [dv0, dv1, [0, 0, 0]], [T1, T2])
        if len(pv_a) == 0:
            return [100.0] * 6
        return [pv_a[0][0] - pv_tgt[0][0], pv_a[0][1] - pv_tgt[0][1],
                pv_a[0][2] - pv_tgt[0][2], pv_a[1][0] - pv_tgt[1][0],
                pv_a[1][1] - pv_tgt[1][1], pv_a[1][2] - pv_tgt[1][2]]

    x0 = np.array([*dv0_seed, 0.0, 0.0, 0.0])
    try:
        sol = least_squares(residual, x0, method="trf", xtol=1e-12,
                            ftol=1e-12, max_nfev=max_nfev)
    except Exception:
        return None
    dv0, dv1 = sol.x[:3], sol.x[3:6]
    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                       [T1, T2])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
           *dv0.tolist(), *dv1.tolist(), *dv2.tolist(), T1, T2]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
             + np.linalg.norm(dv2)) * V
    return -f, dv_ms


def _enumerate(aE, eE, iE, aL, eL, iL, combos):
    """For each (tof_d,rae,age,agl,split,ead,eaa) combo, cheap Lambert |dv0|.
    Returns list of (dv0_norm, combo, pv0, pv_t, tof) sorted ascending,
    Lambert-infeasible (None or >15) dropped."""
    out = []
    for c in combos:
        tof_d, rae, age, agl, split, ead, eaa = c
        tof = tof_d * 86400.0 / T
        pv0 = earth_orbit_state(aE, eE, iE, rae, age, ead)
        pv_t = moon_orbit_state(aL, eL, iL, 0.0, agl, eaa)
        d = lambert_dv0(pv0, pv_t, tof)
        if d is None or not np.all(np.isfinite(d)):
            continue
        nd = float(np.linalg.norm(d))
        if nd > 15:
            continue
        out.append((nd, c, pv0, pv_t, tof))
    out.sort(key=lambda z: z[0])
    return out


def eval_pair(args):
    """Run BASELINE and MULTI-DoF sweep for one (idE,idL). Returns dict.

    Strategy: enumerate all grid combos cheaply via Lambert |dv0|, sort
    ascending, and run the expensive 6-D DC only on the lowest-dv0
    candidates (DC_BUDGET per arm). The DC is the only truth; the Lambert
    sort focuses compute where a positive-mass transfer is plausible."""
    idE, idL = args
    udp = LtlTrajectory(DD)
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    t0 = time.time()

    tofs = [6.0, 9.0, 13.0]
    eas = list(np.linspace(0, 2 * np.pi, 3, endpoint=False))
    DC_BASE = 27    # DC calls allotted to baseline arm
    DC_SWEEP = 90   # DC calls allotted to multi-DoF arm

    # ---- BASELINE combos: raan=argp=0, split=0.5 ----
    base_combos = [(td, 0.0, 0.0, 0.0, 0.5, ead, eaa)
                   for td in tofs for ead in eas for eaa in eas]
    base_cand = _enumerate(aE, eE, iE, aL, eL, iL, base_combos)
    base_best = None
    n_base = 0
    for (_, c, pv0, pv_t, tof) in base_cand[:DC_BASE]:
        r = try_transfer_split(udp, pv0, pv_t, aE, eE, iE, aL, eL, iL,
                               tof, c[4], idE, idL)
        n_base += 1
        if r is not None:
            base_best = r[0] if base_best is None else max(base_best, r[0])

    # ---- MULTI-DoF combos ----
    raan_e_g = list(np.linspace(0, 2 * np.pi, 4, endpoint=False))
    argp_e_g = [0.0, np.pi / 2, np.pi]
    argp_l_g = [0.0, np.pi / 2, np.pi]
    split_g = [0.3, 0.5, 0.7]
    swp_combos = [(td, rae, age, agl, sp, ead, eaa)
                  for td in tofs for rae in raan_e_g for age in argp_e_g
                  for agl in argp_l_g for sp in split_g
                  for ead in eas for eaa in eas]
    swp_cand = _enumerate(aE, eE, iE, aL, eL, iL, swp_combos)
    swp_best = None
    swp_dof = None
    n_swp = 0
    for (nd, c, pv0, pv_t, tof) in swp_cand[:DC_SWEEP]:
        td, rae, age, agl, sp, ead, eaa = c
        r = try_transfer_split(udp, pv0, pv_t, aE, eE, iE, aL, eL, iL,
                               tof, sp, idE, idL)
        n_swp += 1
        if r is not None and (swp_best is None or r[0] > swp_best):
            swp_best = r[0]
            swp_dof = dict(tof=td, raan_e=rae, argp_e=age, argp_l=agl,
                           split=sp, ea_d=ead, ea_a=eaa, dv=r[1],
                           lambert_dv0=nd * V)
    return dict(idE=idE, idL=idL, iE=float(np.degrees(iE)),
                iL=float(np.degrees(iL)), eE=float(eE), eL=float(eL),
                base=base_best, n_base=n_base, swp=swp_best, n_swp=n_swp,
                dof=swp_dof, t=time.time() - t0)


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
    # representative sample across the [60,78] band: pick 8 spread out
    if len(mod) > 8:
        idx = np.linspace(0, len(mod) - 1, 8).astype(int)
        mod = [mod[i] for i in idx]
    pairs = []
    for idEk in mod:
        idLk = min(unusedL, key=lambda k: abs(moon[k, 2] - earth[idEk, 2]))
        pairs.append((idEk, idLk))
    print(f"[E-572] {len(pairs)} moderate-incl pairs to test "
          f"(MAX_NFEV={MAX_NFEV}):", flush=True)
    for (e, l) in pairs:
        print(f"   E{e}(i={iE[e]:.1f}) L{l}(i={np.degrees(moon[l,2]):.1f})",
              flush=True)

    t_all = time.time()
    with Pool(2) as p:
        results = p.map(eval_pair, pairs)

    print("\n" + "=" * 72, flush=True)
    n_unlock = 0
    for r in results:
        base = "FAIL" if r["base"] is None else f"{r['base']:.0f}kg"
        swp = "FAIL" if r["swp"] is None else f"{r['swp']:.0f}kg"
        tag = ""
        if r["base"] is None and r["swp"] is not None:
            tag = "  <<< UNLOCKED"
            n_unlock += 1
        elif (r["base"] is not None and r["swp"] is not None
              and r["swp"] > r["base"] + 1):
            tag = f"  (sweep +{r['swp']-r['base']:.0f}kg)"
        print(f"E{r['idE']}(i={r['iE']:.1f},e={r['eE']:.3f}) "
              f"L{r['idL']}(i={r['iL']:.1f},e={r['eL']:.3f}): "
              f"base={base} sweep={swp} "
              f"[{r['t']:.0f}s,{r['n_base']}+{r['n_swp']} calls]{tag}",
              flush=True)
        if tag.startswith("  <<<") and r["dof"]:
            d = r["dof"]
            print(f"      DoF: tof={d['tof']}d raan_e={d['raan_e']:.2f} "
                  f"argp_e={d['argp_e']:.2f} argp_l={d['argp_l']:.2f} "
                  f"split={d['split']} dv={d['dv']:.0f}m/s", flush=True)

    print("=" * 72, flush=True)
    if n_unlock > 0:
        print(f"[VERDICT] CONFIRMED: {n_unlock}/{len(pairs)} stranded "
              f"moderate-incl pairs UNLOCKED by free DoF.", flush=True)
    else:
        print(f"[VERDICT] REFUTED: 0/{len(pairs)} unlocked. Free DoF do not "
              f"rescue these pairs at this grid resolution.", flush=True)
    print(f"[total wall {time.time()-t_all:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
