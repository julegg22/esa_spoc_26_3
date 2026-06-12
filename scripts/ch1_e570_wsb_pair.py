"""E-570 — WSB second-pair validation (de-risk the fleet sweep).

The E-036/E-565 prototype proved WSB on ONE pair (118,171): 1114 vs 949 kg.
Before committing the multi-day fleet-sweep driver, validate WSB generalizes
to a SECOND pair. This is a thin wrapper that reuses the PROVEN E-565
primitives (phase_a ballistic scan + phase_b3 capture) by monkey-patching the
pair constants — E-565 stays pristine, and the phase-A cache is pair-specific
so the (118,171) cache is never clobbered.

Run: PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
        python -u scripts/ch1_e570_wsb_pair.py IDE IDL IDD BASELINE_KG [n_seed]
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import ch1_e565_wsb_prototype as m
from esa_spoc_26.ch1_trajectory import LtlTrajectory


def main():
    idE, idL, idD, baseline = (int(sys.argv[1]), int(sys.argv[2]),
                               int(sys.argv[3]), float(sys.argv[4]))
    n_seed = int(sys.argv[5]) if len(sys.argv) > 5 else 12

    # monkey-patch the proven prototype's pair globals (functions read them
    # as module globals at call time)
    m.IDE, m.IDL, m.IDD_BANK, m.BASELINE_MASS = idE, idL, idD, baseline

    udp = LtlTrajectory(m.BASE)
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    print(f"E-570 WSB pair ({idE},{idL}) idD={idD} baseline={baseline:.1f} kg",
          flush=True)
    print(f"  aE={aE:.3e} eE={eE:.3f} iE={iE:.3f} | "
          f"aL={aL:.3e} eL={eL:.3f} iL={iL:.3f}", flush=True)

    cache = f"runs/ch1/e570_phaseA_{idE}_{idL}.pkl"
    if os.path.exists(cache):
        cands = pickle.load(open(cache, "rb"))
        print(f"  (phase A cache: {len(cands)} candidates)", flush=True)
    else:
        cands = m.phase_a(udp)
        pickle.dump(cands, open(cache, "wb"))
    if not cands:
        print("=== E-570 RESULT: phase A empty — no bound returns "
              "(WSB outbound geometry not survivable here) ===", flush=True)
        return

    best = m.phase_b3(udp, cands, n_seed=n_seed)
    if best:
        mass, row, info = best
        print(f"\n=== E-570 RESULT: WSB mass {mass:.1f} kg vs baseline "
              f"{baseline:.1f} kg ({mass - baseline:+.1f}) ===", flush=True)
        # CRITICAL: dump at FULL float64 precision. BCP is chaotic over the
        # ~99d WSB arc, so rounding the initial state to 12 decimals shifts
        # the arrival (a,e,i) match past the official 1e-6 tol and destroys
        # an otherwise-valid solution.
        rowf = [float(v) for v in row]
        out = f"runs/ch1/e570_row_{idE}_{idL}.json"
        json.dump({"idE": idE, "idL": idL, "idD": idD, "baseline": baseline,
                   "wsb_mass": mass, "row": rowf}, open(out, "w"))
        print(f"  full-precision row -> {out}", flush=True)
        print("row(repr):", [repr(v) for v in rowf], flush=True)
    else:
        print("\n=== E-570 RESULT: no valid WSB capture found ===",
              flush=True)


if __name__ == "__main__":
    main()
