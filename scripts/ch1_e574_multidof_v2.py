"""E-574 — CORRECTED multi-DoF feasibility test for stranded high-incl Ch1
pairs, with a SELF-VALIDATION GATE.

E-572 concluded REFUTED, but E-573 proved its harness was broken: it FAILED
to reproduce E0->L0 (a coplanar bank pair, 819 kg). Root cause (from bank
inspection): the bank's real transfers use tof median 4.7d (range 0.9-35.6d)
and split median 0.943 (many at 1.0) -- E-572's grid tof{6,9,13}d x
split{0.3,0.5,0.7} missed BOTH regions, so both arms failed for grid reasons,
not DoF reasons.

This corrected test:
  * tof grid covers the bank's real range (dense 1-6d + a few longer).
  * split swept up to 1.0 (near-single-arc, where the bank lives).
  * max_nfev=100 (full DC budget), early-exit on first feasible per arm.
  * BASELINE = raan_e=argp_e=raan_l=argp_l=0 but SWEEP tof/split/ea
    (matches what the REAL solver can already do; the bank disproves the
    "split=0.5 hardcoded" premise -- the genuinely-pinned DoF are raan/argp).
  * SWEEP = additionally vary raan_e, argp_e, argp_l (the truly-free DoF).

HARD GATE: first reproduce >=4/5 KNOWN-FEASIBLE bank pairs with the BASELINE
arm. Only if the gate passes do we trust a stranded-pair FAIL->FEASIBLE flip.
Read-only; writes NOTHING to solutions.
"""
from __future__ import annotations

import json
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
MAX_NFEV = 100

# tof grid: dense over the bank's bulk (0.9-6d) + a few longer tails.
TOFS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 9.0, 13.0, 20.0]
EAS = list(np.linspace(0, 2 * np.pi, 3, endpoint=False))
SPLITS = [0.5, 0.7, 0.85, 0.95, 1.0]
DC_CAP = 60  # max DC calls per arm (early-exit on first feasible)


def try_transfer_split(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                       split, idE, idL):
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
                            ftol=1e-12, max_nfev=MAX_NFEV)
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
    return -f


def _enum(aE, eE, iE, aL, eL, iL, combos):
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


def _run_arm(udp, idE, idL, combos):
    """Lambert-sort combos, run DC (cap DC_CAP), EARLY-EXIT on first
    feasible. Returns (best_mass_or_None, n_dc_calls, dof_dict_or_None)."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    cand = _enum(aE, eE, iE, aL, eL, iL, combos)
    n = 0
    for (nd, c, pv0, pv_t, tof) in cand[:DC_CAP]:
        td, rae, age, agl, sp, ead, eaa = c
        r = try_transfer_split(udp, pv0, pv_t, aE, eE, iE, aL, eL, iL,
                               tof, sp, idE, idL)
        n += 1
        if r is not None:
            return r, n, dict(tof=td, raan_e=rae, argp_e=age, argp_l=agl,
                              split=sp, lambert_dv0=nd * V)
    return None, n, None


def baseline_combos():
    # raan/argp pinned 0; sweep tof, split, ea (what the real solver does).
    return [(td, 0.0, 0.0, 0.0, sp, ead, eaa)
            for td in TOFS for sp in SPLITS for ead in EAS for eaa in EAS]


def sweep_combos():
    raan_e_g = list(np.linspace(0, 2 * np.pi, 4, endpoint=False))
    argp_g = [0.0, np.pi / 2, np.pi]
    eas2 = list(np.linspace(0, 2 * np.pi, 2, endpoint=False))
    return [(td, rae, age, agl, sp, ead, eaa)
            for td in TOFS for rae in raan_e_g for age in argp_g
            for agl in argp_g for sp in SPLITS for ead in eas2 for eaa in eas2]


def _val_one(args):
    idE, idL, bank_mass = args
    udp = LtlTrajectory(DD)
    t0 = time.time()
    best, n, _ = _run_arm(udp, idE, idL, baseline_combos())
    return (idE, idL, bank_mass, best, n, time.time() - t0,
            float(np.degrees(udp.earth_data[idE][2])),
            float(np.degrees(udp.moon_data[idL][2])))


def _stranded_one(args):
    idE, idL = args
    udp = LtlTrajectory(DD)
    t0 = time.time()
    base, nb, _ = _run_arm(udp, idE, idL, baseline_combos())
    swp, ns, dof = (None, 0, None)
    if base is None:  # only worth sweeping if baseline genuinely fails
        swp, ns, dof = _run_arm(udp, idE, idL, sweep_combos())
    return dict(idE=idE, idL=idL,
                iE=float(np.degrees(udp.earth_data[idE][2])),
                iL=float(np.degrees(udp.moon_data[idL][2])),
                base=base, nb=nb, swp=swp, ns=ns, dof=dof,
                t=time.time() - t0)


def main():
    udp = LtlTrajectory(DD)
    earth, moon = udp.earth_data, udp.moon_data
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0][
        "decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    used = [(int(r[0]), int(r[1]), -udp.fitness(list(r))[0])
            for r in rows if r[0] >= 0]
    usedE = set(t[0] for t in used)
    usedL = set(t[1] for t in used)
    iEdeg = np.degrees(earth[:, 2])

    # ---- self-validation set: 5 known-feasible pairs spread by Earth incl
    used.sort(key=lambda t: earth[t[0]][2])
    vidx = np.linspace(0, len(used) - 1, 5).astype(int)
    valset = [used[i] for i in vidx]

    print(f"[E-574] GATE: validating BASELINE arm on 5 known-feasible bank "
          f"pairs (tof{len(TOFS)} x split{len(SPLITS)} x ea3, nfev={MAX_NFEV})",
          flush=True)
    t0 = time.time()
    with Pool(2) as p:
        vres = p.map(_val_one, valset)
    n_ok = 0
    for (idE, idL, bm, best, n, dt, iE, iL) in vres:
        ok = best is not None
        n_ok += ok
        print(f"  E{idE}(i={iE:.1f}) L{idL}(i={iL:.1f}) bank={bm:.0f}kg -> "
              f"baseline={'FAIL' if best is None else f'{best:.0f}kg'} "
              f"({n} DC,{dt:.0f}s) {'OK' if ok else '<<< MISS'}", flush=True)
    print(f"[GATE] {n_ok}/5 known-feasible recovered "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if n_ok < 4:
        print("[ABORT] harness STILL too weak (<4/5) -> widen grid before "
              "trusting any stranded-pair result. NOT testing stranded pairs.",
              flush=True)
        return

    # ---- stranded high-incl pairs: pair each unused hi-incl Earth with the
    # nearest-incl unused Moon. Test a spread across 55-90 deg.
    unusedE = [k for k in range(len(earth)) if k not in usedE]
    unusedL = [k for k in range(len(moon)) if k not in usedL]
    hi = sorted([k for k in unusedE if iEdeg[k] >= 55], key=lambda k: iEdeg[k])
    sidx = np.linspace(0, len(hi) - 1, 6).astype(int)
    strand = []
    for k in [hi[i] for i in sidx]:
        l = min(unusedL, key=lambda m: abs(moon[m, 2] - earth[k, 2]))
        strand.append((k, l))
    print(f"\n[E-574] GATE PASSED -> testing {len(strand)} stranded pairs "
          f"(baseline vs full multi-DoF sweep)", flush=True)
    t0 = time.time()
    with Pool(2) as p:
        sres = p.map(_stranded_one, strand)
    print("=" * 72, flush=True)
    n_unlock = 0
    for r in sres:
        base = "FAIL" if r["base"] is None else f"{r['base']:.0f}kg"
        swp = "n/a" if r["base"] is not None else (
            "FAIL" if r["swp"] is None else f"{r['swp']:.0f}kg")
        tag = ""
        if r["base"] is None and r["swp"] is not None:
            tag = "  <<< UNLOCKED by free DoF"
            n_unlock += 1
        print(f"E{r['idE']}(i={r['iE']:.1f}) L{r['idL']}(i={r['iL']:.1f}): "
              f"baseline={base} sweep={swp} "
              f"[{r['nb']}+{r['ns']} DC,{r['t']:.0f}s]{tag}", flush=True)
        if tag and r["dof"]:
            d = r["dof"]
            print(f"      DoF: tof={d['tof']}d raan_e={d['raan_e']:.2f} "
                  f"argp_e={d['argp_e']:.2f} argp_l={d['argp_l']:.2f} "
                  f"split={d['split']}", flush=True)
    print("=" * 72, flush=True)
    if n_unlock:
        print(f"[VERDICT] CONFIRMED: free RAAN/argp DoF UNLOCK {n_unlock}/"
              f"{len(strand)} stranded pairs that the real solver cannot reach "
              f"-> build 99-slot re-solve campaign.", flush=True)
    else:
        all_base_feas = sum(r["base"] is not None for r in sres)
        print(f"[VERDICT] REFUTED (now TRUSTWORTHY, gate passed): 0 unlocked. "
              f"{all_base_feas}/{len(strand)} were already baseline-feasible "
              f"(=> they're unfilled by ASSIGNMENT, not infeasibility); the "
              f"rest are genuinely infeasible even with free DoF.", flush=True)
    print(f"[stranded wall {time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
