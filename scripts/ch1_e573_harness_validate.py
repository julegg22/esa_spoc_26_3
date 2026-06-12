"""E-573 — VALIDATE the E-572 harness before trusting its REFUTED verdict.

E-572 concluded the RAAN/argp/split free-DoF lead is REFUTED because both
the baseline AND the multi-DoF sweep FAILED on all 8 stranded moderate-incl
pairs. But the baseline failing is only meaningful if the harness
(max_nfev=40, tof grid {6,9,13}d, 27 baseline DC calls) is actually strong
enough to FIND a feasible transfer when one exists.

Methodology trigger: AUDIT THE EVALUATOR. Run the EXACT baseline arm of the
E-572 harness on pairs that are KNOWN-FEASIBLE (they are filled in the bank
with positive mass). If the harness recovers positive mass on those -> it is
adequate and REFUTED stands. If it FAILS on known-feasible pairs -> the
harness is too weak and the REFUTED verdict is unreliable (both arms fail
for lack of solver budget, not lack of DoF).
"""
import importlib.util
import json
import sys

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")

spec = importlib.util.spec_from_file_location(
    "e572", f"{ROOT}/scripts/ch1_e572_multidof_feas.py")
e572 = importlib.util.module_from_spec(spec)
sys.modules["e572"] = e572
spec.loader.exec_module(e572)

from esa_spoc_26.ch1_trajectory import LtlTrajectory, T  # noqa: E402

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def baseline_arm(udp, idE, idL):
    """Reproduce E-572's baseline arm exactly: raan=argp=0, split=0.5,
    tof x ea grid, Lambert-prefiltered, up to DC_BASE 6-D DC calls."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    tofs = [6.0, 9.0, 13.0]
    eas = list(np.linspace(0, 2 * np.pi, 3, endpoint=False))
    base_combos = [(td, 0.0, 0.0, 0.0, 0.5, ead, eaa)
                   for td in tofs for ead in eas for eaa in eas]
    cand = e572._enumerate(aE, eE, iE, aL, eL, iL, base_combos)
    best = None
    n = 0
    for (_, c, pv0, pv_t, tof) in cand[:27]:
        r = e572.try_transfer_split(udp, pv0, pv_t, aE, eE, iE, aL, eL, iL,
                                    tof, c[4], idE, idL)
        n += 1
        if r is not None:
            best = r[0] if best is None else max(best, r[0])
    return best, n, float(np.degrees(iE)), float(np.degrees(iL))


def main():
    udp = LtlTrajectory(DD)
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0][
        "decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    used = [(int(r[0]), int(r[1]), udp.fitness(list(r))[0])
            for r in rows if r[0] >= 0]
    # sort by Earth inclination ascending; sample low, mid, high used incls
    used.sort(key=lambda t: udp.earth_data[t[0]][2])
    idx = np.linspace(0, len(used) - 1, 6).astype(int)
    sample = [used[i] for i in idx]
    print(f"[E-573] validating E-572 baseline arm on {len(sample)} "
          f"KNOWN-FEASIBLE bank pairs (banked mass shown):", flush=True)
    n_ok = 0
    for (idE, idL, bankf) in sample:
        bank_mass = -bankf  # fitness returns [-mass]
        best, n, iEd, iLd = baseline_arm(udp, idE, idL)
        ok = best is not None
        n_ok += ok
        print(f"  E{idE}(i={iEd:.1f}) L{idL}(i={iLd:.1f}) bank={bank_mass:.0f}kg "
              f"-> harness baseline={'FAIL' if best is None else f'{best:.0f}kg'} "
              f"({n} DC calls) {'OK' if ok else '<<< HARNESS MISSED A KNOWN-FEASIBLE PAIR'}",
              flush=True)
    print("=" * 60, flush=True)
    if n_ok == len(sample):
        print(f"[VERDICT] harness ADEQUATE ({n_ok}/{len(sample)} known-feasible "
              f"recovered) -> E-572 REFUTED is TRUSTWORTHY.", flush=True)
    else:
        print(f"[VERDICT] harness TOO WEAK ({n_ok}/{len(sample)} recovered) "
              f"-> E-572 REFUTED is UNRELIABLE; both arms fail for lack of "
              f"solver budget, not lack of DoF. Re-test with max_nfev>=100 + "
              f"finer tof grid before concluding.", flush=True)


if __name__ == "__main__":
    main()
