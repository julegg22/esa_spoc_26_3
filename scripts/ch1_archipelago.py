"""E-692: strong STOCHASTIC global optimizer (CMA-ES archipelago) on the per-pair BCP problem.
E-605 Exp 1, never properly run. My deterministic solvers (DC/shooting) all give bank-or-worse;
a multi-island CMA-ES seeded from the feasible bank + Hohmann may escape the bank's mediocre basin.
DECISIVE: does any island beat the bank's per-pair dv on the expensive pairs?

Usage: python ch1_archipelago.py [n=6] [gen=250] [islands=8]
"""
import sys, json, math, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_pair_udp import PairUDP, multi_seed_pop, bank_to_seed
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main(n=6, gen=250, islands=8):
    print("[E-692] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]; V = 3.84405e8 / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    cands = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        if eL[l] >= 0.1:                          # non-circular (PairUDP arrival works)
            dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
            cands.append((dv, e, l, r))
    cands.sort(reverse=True)
    picks = cands[:n]
    print(f"[E-692] CMA-ES archipelago ({islands} islands x gen {gen}) on {n} expensive non-circular pairs", flush=True)
    print(f"  {'pair':>12} {'bank':>7}  {'archi':>7} {'Δ':>7} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0
    for bank_dv, e, l, br in picks:
        prob = pg.problem(PairUDP(udp, e, l))
        algo = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-6, xtol=1e-6))
        archi = pg.archipelago()
        for k in range(islands):
            pop = multi_seed_pop(prob, udp, e, l, pop_size=24, bank_row=br,
                                 rng=np.random.default_rng(7 * e + 13 * l + 101 * k))
            archi.push_back(pg.island(algo=algo, pop=pop))
        archi.evolve(2); archi.wait()
        best = min(float(isl.get_population().champion_f[0]) for isl in archi)
        d = bank_dv - best if best < 1e5 else float("nan")
        hit = best < 1e5 and d > 50; wins += hit
        bs = f"{best:7.0f}" if best < 1e5 else "  FAIL"
        print(f"  ({e:>4},{l:>4}) {bank_dv:7.0f}  {bs} {d:+7.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-692] VERDICT: {wins}/{n} pairs beaten by CMA-ES archipelago", flush=True)
    print("  >0 -> stochastic global search escapes the bank's basin -> per-pair lever ALIVE, scale fleet", flush=True)
    print("  0  -> even strong stochastic search can't beat the bank -> bank near the BCP per-pair floor (within our reach)", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6,
         int(sys.argv[2]) if len(sys.argv) > 2 else 250,
         int(sys.argv[3]) if len(sys.argv) > 3 else 8)
