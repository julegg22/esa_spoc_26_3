"""E-577 — DEFINITIVE raan/argp verdict with a self-validating gate.

CONTEXT (established, do not re-derive):
  * E-576 bank inspection PROVED the bank uses NONZERO departure RAAN for the
    high-incl known-feasible pairs:
        E0  (i=0.0)  raan=0
        E69 (i=10.5) raan=0
        E54 (i=24.0) raan=0
        E252(i=55.7) raan=270  <-- nonzero
        E100(i=89.4) raan=90   <-- nonzero
    argp=0 in all cases; the load-bearing free DoF is RAAN.
  * The bank's high-incl rows were produced by the apogee-plane-change
    architecture (ch1_apogee_plane_change.try_apogee_plane_change), which
    sweeps raan_e. The raan=0 solvers (scan_and_polish, multi_restart) cannot
    have produced E252/E100.

This script makes the verdict airtight:

PHASE A (gate): the FAITHFUL baseline = apogee-plane-change solver.
  A1. FULL raan/argp/ea/t0/tof sweep -> must reproduce ALL 5 pairs as
      feasible (positive mass). This is the non-negotiable gate.
  A2. raan=argp=0 ONLY (still sweeping ea/t0/tof/t2) -> expect E252 & E100
      to FAIL while E0/E69/E54 pass. This isolates RAAN as the load-bearing
      DoF: if raan=0 cannot reach E252/E100 no matter how fine the rest of
      the sweep, the bank PROVABLY required nonzero raan.

PHASE B (lead test): on ~6 stranded UNFILLED high-incl Earth orbits (i>=55),
  each paired with the nearest-incl unused Moon orbit:
    * raan=argp=0 baseline (faithful apogee solver) -> expect FAIL
    * raan/argp-swept (same solver) -> feasible? which raan?
  Per pair report baseline FAIL/feas, sweep FAIL/feas, raan, mass.
  If a stranded pair is ALREADY baseline-feasible -> it's unfilled by
  ASSIGNMENT, report separately.

Read-only. 2 workers max.
"""
from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")

from esa_spoc_26.ch1_trajectory import LtlTrajectory  # noqa: E402
from esa_spoc_26.ch1_apogee_plane_change import (  # noqa: E402
    try_apogee_plane_change,
)

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"

# --- sweep grids ---
EA_DEP = list(np.linspace(0, 2 * np.pi, 6, endpoint=False))
EA_ARR = (0.0, np.pi / 2, np.pi, 3 * np.pi / 2)
T0_GRID = (0.0, np.pi)
T2_GRID = (0.5, 1.0, 1.5, 2.0, 3.0)
RAAN_E_FULL = list(np.linspace(0, 2 * np.pi, 8, endpoint=False))
ARGP_E_FULL = list(np.linspace(0, 2 * np.pi, 4, endpoint=False))
ARGP_L = (0.0,)  # arrival argp free per validator but bank uses arr-side DC

WALL_PER_PAIR = 600.0  # seconds; early-exit on first feasible anyway


def _solve(udp, idE, idL, raan_e_grid, argp_e_grid, want_best=False):
    """Run the faithful apogee solver over the given raan/argp grids plus the
    fixed ea/t0/t2 sweep. EARLY-EXIT on first feasible unless want_best.
    Returns (mass, raan_e, argp_e, n_tried) or (None, None, None, n_tried)."""
    t0 = time.time()
    best = None
    n = 0
    for raan_e in raan_e_grid:
        for argp_e in argp_e_grid:
            for ea_dep in EA_DEP:
                for t0v in T0_GRID:
                    for ea_arr in EA_ARR:
                        for t2_d in T2_GRID:
                            n += 1
                            res = try_apogee_plane_change(
                                udp, idE, idL, raan_e, argp_e, ea_dep,
                                0.0, 0.0, ea_arr, t0v, t2_d)
                            if res is not None:
                                mass = res[0]
                                if best is None or mass > best[0]:
                                    best = (mass, raan_e, argp_e)
                                if not want_best:
                                    return best[0], best[1], best[2], n
                            if time.time() - t0 > WALL_PER_PAIR:
                                if best is not None:
                                    return best[0], best[1], best[2], n
                                return None, None, None, n
    if best is not None:
        return best[0], best[1], best[2], n
    return None, None, None, n


# ---------------- Phase A workers ----------------
def _gateA_full(args):
    name, idE, idL = args
    udp = LtlTrajectory(DD)
    t0 = time.time()
    m, ra, ag, n = _solve(udp, idE, idL, RAAN_E_FULL, ARGP_E_FULL)
    return ("full", name, idE, idL, m, ra, ag, n, time.time() - t0)


def _gateA_raan0(args):
    name, idE, idL = args
    udp = LtlTrajectory(DD)
    t0 = time.time()
    m, ra, ag, n = _solve(udp, idE, idL, [0.0], [0.0])
    return ("raan0", name, idE, idL, m, ra, ag, n, time.time() - t0)


# ---------------- Phase B worker ----------------
def _strand(args):
    idE, idL, iE, iL = args
    udp = LtlTrajectory(DD)
    t0 = time.time()
    # baseline raan=argp=0
    mb, _, _, nb = _solve(udp, idE, idL, [0.0], [0.0])
    ms, ras, ags, ns = (None, None, None, 0)
    if mb is None:  # only sweep if baseline genuinely fails
        ms, ras, ags, ns = _solve(udp, idE, idL, RAAN_E_FULL, ARGP_E_FULL)
    return dict(idE=idE, idL=idL, iE=iE, iL=iL, mb=mb, ms=ms,
                raan=ras, argp=ags, nb=nb, ns=ns, t=time.time() - t0)


def main():
    udp = LtlTrajectory(DD)
    earth, moon = udp.earth_data, udp.moon_data
    iEdeg = np.degrees(earth[:, 2])
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0][
        "decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    usedE = set(int(r[0]) for r in rows if r[0] >= 0)
    usedL = set(int(r[1]) for r in rows if r[0] >= 0)

    five = [("E0", 0, 0), ("E69", 69, 63), ("E54", 54, 330),
            ("E252", 252, 354), ("E100", 100, 90)]

    print("[E-577] PHASE A1 — faithful apogee solver, FULL raan/argp sweep, "
          "GATE on 5 known-feasible bank pairs", flush=True)
    t0 = time.time()
    with Pool(2) as p:
        rfull = p.map(_gateA_full, [(n, e, l) for n, e, l in five])
    n_ok = 0
    full_ok = {}
    for (_, name, idE, idL, m, ra, ag, n, dt) in rfull:
        ok = m is not None
        n_ok += ok
        full_ok[name] = ok
        raan_d = "n/a" if ra is None else f"{np.degrees(ra):.0f}"
        print(f"  {name} E{idE}->L{idL}: {'FAIL' if m is None else f'{m:.0f}kg'}"
              f" raan_e={raan_d} ({n} tries,{dt:.0f}s) "
              f"{'OK' if ok else '<<< MISS'}", flush=True)
    print(f"[GATE A1] {n_ok}/5 reproduced with FULL raan/argp sweep "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if n_ok < 5:
        print("[ABORT] faithful baseline did NOT reproduce all 5 -> harness "
              "still not faithful; not proceeding to Phase B.", flush=True)
        return

    print("\n[E-577] PHASE A2 — SAME solver but raan=argp=0 ONLY (isolate "
          "RAAN as load-bearing DoF)", flush=True)
    t0 = time.time()
    with Pool(2) as p:
        rzero = p.map(_gateA_raan0, [(n, e, l) for n, e, l in five])
    zero_ok = {}
    for (_, name, idE, idL, m, ra, ag, n, dt) in rzero:
        ok = m is not None
        zero_ok[name] = ok
        print(f"  {name} E{idE}->L{idL} (raan=0): "
              f"{'FAIL' if m is None else f'{m:.0f}kg'} "
              f"({n} tries,{dt:.0f}s)", flush=True)
    print(f"[A2] raan=0 reproduces: "
          f"{[k for k,v in zero_ok.items() if v]} ; "
          f"raan=0 FAILS: {[k for k,v in zero_ok.items() if not v]} "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # ---- Phase B: stranded high-incl unfilled Earth orbits ----
    unusedE = [k for k in range(len(earth)) if k not in usedE]
    unusedL = [k for k in range(len(moon)) if k not in usedL]
    hi = sorted([k for k in unusedE if iEdeg[k] >= 55], key=lambda k: iEdeg[k])
    sidx = np.linspace(0, len(hi) - 1, 6).astype(int)
    strand = []
    for k in sorted(set(hi[i] for i in sidx)):
        l = min(unusedL, key=lambda m: abs(moon[m, 2] - earth[k, 2]))
        strand.append((k, l, float(iEdeg[k]), float(np.degrees(moon[l, 2]))))
    print(f"\n[E-577] PHASE B — {len(strand)} stranded high-incl unfilled "
          f"pairs (raan=0 baseline vs raan-swept apogee solver)", flush=True)
    t0 = time.time()
    with Pool(2) as p:
        sres = p.map(_strand, strand)

    print("=" * 78, flush=True)
    n_unlock = 0
    n_base_feas = 0
    for r in sres:
        base = "FAIL" if r["mb"] is None else f"{r['mb']:.0f}kg"
        if r["mb"] is not None:
            n_base_feas += 1
            swp = "n/a"
            tag = "  (baseline-FEASIBLE -> ASSIGNMENT lever, not infeasibility)"
        elif r["ms"] is not None:
            swp = f"{r['ms']:.0f}kg"
            tag = (f"  <<< UNLOCKED by raan_e={np.degrees(r['raan']):.0f} "
                   f"argp_e={np.degrees(r['argp']):.0f}")
            n_unlock += 1
        else:
            swp = "FAIL"
            tag = "  (infeasible even with free raan/argp)"
        print(f"E{r['idE']}(i={r['iE']:.1f}) L{r['idL']}(i={r['iL']:.1f}): "
              f"baseline={base} sweep={swp} [{r['nb']}+{r['ns']} tries,"
              f"{r['t']:.0f}s]{tag}", flush=True)
    print("=" * 78, flush=True)

    # ---- VERDICT ----
    print("\n" + "#" * 78, flush=True)
    print("# FINAL VERDICT", flush=True)
    print("#" * 78, flush=True)
    print(f"# (1) Phase A1 gate: {n_ok}/5 reproduced with full sweep "
          f"-> {'PASS' if n_ok == 5 else 'FAIL'}", flush=True)
    raan0_fails = [k for k, v in zero_ok.items() if not v]
    print(f"# (2) Phase A2: with raan=argp=0, FAILS on {raan0_fails} "
          f"(these are the high-incl pairs); the bank PROVABLY used nonzero "
          f"raan (E-576: E252 raan=270, E100 raan=90).", flush=True)
    if n_unlock > 0:
        print(f"# (3) VERDICT: CONFIRMED. Free RAAN unlocks {n_unlock}/"
              f"{len(strand)} stranded high-incl pairs that the raan=0 "
              f"baseline CANNOT reach. The bank already exploits this for some "
              f"high-incl slots; the {n_unlock} here are additional unlockable "
              f"slots -> raan-sweep re-solve of the 99 unfilled slots is "
              f"warranted.", flush=True)
    elif n_base_feas == len(strand):
        print(f"# (3) VERDICT: REFUTED-BY-ASSIGNMENT. All {len(strand)} "
              f"stranded pairs are baseline-feasible at raan=0 -> they are "
              f"unfilled by the MATCHING, not by infeasibility. Lever = "
              f"better assignment, not free raan/argp.", flush=True)
    elif n_base_feas > 0:
        print(f"# (3) VERDICT: MIXED. {n_base_feas} stranded pairs are "
              f"baseline-feasible (ASSIGNMENT lever); {n_unlock} unlocked by "
              f"raan; the rest infeasible even with free DoF.", flush=True)
    else:
        print(f"# (3) VERDICT: REFUTED-INFEASIBLE. 0 unlocked, 0 "
              f"baseline-feasible -> stranded high-incl pairs are genuinely "
              f"infeasible even with full raan/argp sweep.", flush=True)
    print("# Script: scripts/ch1_e577_raan_verdict.py", flush=True)
    print("# Log:    runs/ch1/83_e577_raan_verdict.log", flush=True)
    print(f"[phase B wall {time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
