"""E-683: is the bank's CIRCULAR-capture dv at the per-pair IMPULSIVE floor, or did our solver
leave headroom? (2026-06-21, redirected from the WSB probe.)

Geometry check killed the WSB angle: the 250 circular (eL<0.1) Moon orbits are DEEP low LLO
(a/SOI=0.029, ~1.1 R_moon, ~190 km alt) — too deep for Sun-assisted ballistic capture (E-604's
"narrow window" is real physics). But low-circular-LLO insertion is impulsive anyway (Hohmann +
perilune circularization ~3975 m/s by hand), yet the bank sits ~4900 on these. So the open
question is IMPULSIVE solver quality, not exotic physics.

THIS PROBE: take the bank's most-expensive CIRCULAR pairs (eL<0.1, high dv), run a FRESH global
search (multi_seed_pop WITHOUT the bank row — Hohmann multi-phasing + random, ORIGINAL short-time
bounds, fast) on the impulsive PairUDP. Does it find dv well BELOW the bank's ~4900?
  YES (e.g. ~3975) -> our impulsive solver left the circular captures suboptimal -> lever is
       better per-pair impulsive solving (tractable, fits the deadline) -> mass headroom ~+89k.
  NO  (~bank) -> bank is at the impulsive floor for deep circular capture -> gap is elsewhere /
       genuinely needs a mechanism we don't have -> re-audit.

Usage: python ch1_circular_impulsive_floor.py [n_pairs=6] [gen=150]
"""
import sys, json, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_pair_udp import PairUDP, multi_seed_pop
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main(n_pairs=6, gen=150):
    print("[E-683] init: heyoka BCP + orbits ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    Vunit = 3.84405e8 / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    cands = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        if eL[l] >= 0.1:                       # circular targets only
            continue
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
        cands.append((dv, e, l))
    cands.sort(reverse=True)
    picks = cands[:n_pairs]
    print(f"[E-683] {len(cands)} circular(eL<0.1) bank pairs; FRESH (non-bank) impulsive search on {n_pairs} most expensive", flush=True)
    print(f"  per-pair Hohmann-multiphasing + random seeds, sade gen={gen} (original short-time bounds)", flush=True)
    print(f"  DECISIVE: does fresh search beat the bank's circular dv (toward ~3975 hand-estimate)?", flush=True)
    print(f"  {'pair':>12} {'bank_dv':>8}  {'fresh_dv':>8} {'Δdv':>7} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); improved = 0; tot = 0.0
    for bank_dv, e, l in picks:
        prob = pg.problem(PairUDP(udp, e, l))
        algo = pg.algorithm(pg.sade(gen=gen, ftol=0.0, xtol=0.0))
        best = float("inf")
        for restart in range(2):
            pop = multi_seed_pop(prob, udp, e, l, pop_size=30, bank_row=None,
                                 rng=np.random.default_rng(7 * e + 13 * l + 101 * restart))
            pop = algo.evolve(pop)
            if pop.champion_f[0] < best:
                best = float(pop.champion_f[0])
        d = bank_dv - best
        hit = d > 50
        improved += hit; tot += max(d, 0)
        print(f"  ({e:>4},{l:>4}) {bank_dv:8.0f}  {best:8.0f} {d:+7.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-683] VERDICT: {improved}/{n_pairs} circular pairs beaten by fresh impulsive search; mean Δdv={tot/n_pairs:.0f} m/s", flush=True)
    print("  >0 substantially -> impulsive headroom on circular captures -> better per-pair solving is the lever (tractable)", flush=True)
    print("  ~0 -> bank at impulsive floor for deep circular LLO -> gap genuinely elsewhere -> re-audit", flush=True)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    g = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    main(n, g)
