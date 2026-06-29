"""Audit attack on 'moderate-TOF rows officially infeasible = cold-start wall' (E-757).
The official feasibility check (_validate_transfer) requires the forward-propagated end state to match
the target Moon orbit (a,e,i) to 1e-6 (_match_orbit). Question: do the moderate-TOF solutions MISS by
a lot (real infeasibility) or by a little (a convergence/precision miss closeable by differential
correction)? Measure the residual on the EXISTING cached moderate rows (closure uses idE,idL only — idD
irrelevant, so the idD=0 caches are fine for this)."""
import sys, json, glob
import numpy as np
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import (LtlTrajectory, propagate, state2earth, state2moon, L, V, T as TUNIT)
import pykep as pk
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def closure(idE, idL, row):
    t0 = row[3]; pv0 = [[row[4], row[5], row[6]], [row[7], row[8], row[9]]]
    DVs = [[row[10], row[11], row[12]], [row[13], row[14], row[15]], [row[16], row[17], row[18]]]
    Ts = [row[19], row[20]]
    aE, eE, iE = udp.earth_data[idE]; aL, eL, iL = udp.moon_data[idL]
    e0 = state2earth(pv0)
    pv1 = propagate([list(pv0[0]), list(pv0[1])], t0, DVs, Ts)
    if len(pv1) == 0:
        return None
    e1 = state2moon(pv1)
    return {
        "earth_da": abs(e0[0] - aE) / L, "earth_de": abs(e0[1] - eE), "earth_di": abs(e0[2] - iE),
        "moon_da": abs(e1[0] - aL) / L, "moon_de": abs(e1[1] - eL), "moon_di": abs(e1[2] - iL),
        "tof_d": (Ts[0] + Ts[1]) * TUNIT * pk.SEC2DAY,
    }


def main():
    rows = []
    for f in sorted(glob.glob("cache/ch1_moderate_fleet_w*of3.json")) + sorted(glob.glob("cache/ch1_moderate_v2_fleet_w*of3.json")):
        for e in json.load(open(f)):
            if "row" in e:
                rows.append((e["idE"], e["idL"], e["row"], e.get("gain", 0)))
    print(f"[probe] {len(rows)} cached moderate rows; tolerance for VALID = 1e-6 on each of a/e/i", flush=True)
    print(f"{'pair':>14} {'tof_d':>6} | {'moon_da':>9} {'moon_de':>9} {'moon_di':>9} | {'earth_da':>9} {'earth_de':>9} {'earth_di':>9}", flush=True)
    for idE, idL, row, gain in rows[:12]:
        c = closure(idE, idL, row)
        if c is None:
            print(f"({idE:>4},{idL:>4}) propagate FAILED (len 0)", flush=True); continue
        worst = max(c["moon_da"], c["moon_de"], c["moon_di"])
        flag = "<<NEAR (corrector could close)" if worst < 1e-2 else ("<miss" if worst < 1.0 else "BIG MISS")
        print(f"({idE:>4},{idL:>4}) {c['tof_d']:6.1f} | {c['moon_da']:9.2e} {c['moon_de']:9.2e} {c['moon_di']:9.2e} | "
              f"{c['earth_da']:9.2e} {c['earth_de']:9.2e} {c['earth_di']:9.2e} {flag}", flush=True)


if __name__ == "__main__":
    main()
