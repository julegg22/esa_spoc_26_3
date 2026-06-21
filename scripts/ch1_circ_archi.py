"""E-695: AUDIT-driven — the expensive CIRCULAR pairs (dv2 inflated to 1700-2434 vs ~800 floor)
were NEVER optimized by a working solver (PairUDP uses solve_arrival_eccentric which fails circular;
the archipelago ran only on eL>=0.1). Build a circular-capable PairUDP (solve_arrival_dv) and run a
strong CMA-ES archipelago, seeded BROADLY incl long-tof slow arrivals. Does dv2/total drop below bank?
"""
import sys, json, math, time
import numpy as np
import pygmo as pg
import heyoka as hy
import pykep as pk
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import (LtlTrajectory, earth_orbit_state, propagate, V, T, L)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
from esa_spoc_26.ch1_pair_udp import bank_to_seed
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi
PEN = 1e6


class PairUDPCirc:
    """per-pair UDP using solve_arrival_dv (works for circular). Extended tof bounds for slow arrivals."""
    def __init__(self, udp, idE, idL):
        self.udp = udp; self.idE = idE; self.idL = idL
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aM, self.eM, self.iM = udp.moon_data[idL]

    def get_bounds(self):
        lb = [0, 0, 0, 0, 0.05, 0.0, -5, -5, -5, -5, -5, -5]
        ub = [TWO_PI, TWO_PI, TWO_PI, TWO_PI, 20.0, 6.0, 5, 5, 5, 5, 5, 5]  # T1<=~87d, T2<=~26d
        return (lb, ub)

    def fitness(self, x):
        raan_e, argp_e, ea, t0, T1, T2 = x[:6]
        dv0 = x[6:9]; dv1 = x[9:12]
        if T1 < 0.05 or T2 < 0:
            return [PEN]
        try:
            pv0 = earth_orbit_state(self.aE, self.eE, self.iE, raan_e, argp_e, ea)
            pv1 = propagate(pv0, t0, [list(dv0), list(dv1), [0, 0, 0]], [T1, T2])
        except Exception:
            return [PEN]
        if len(pv1) == 0:
            return [PEN]
        a2 = solve_arrival_dv(pv1, self.aM, self.eM, self.iM)
        if a2 is None:
            return [PEN]
        dv2 = a2[0]
        tot = (np.linalg.norm(dv0) + np.linalg.norm(dv1) + np.linalg.norm(dv2)) * V
        if tot > 12000:
            return [PEN]
        return [tot]


def main(pairs):
    print("[E-695] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    bankrows = {}
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        bankrows[(int(r[0]), int(r[1]))] = (dv, r)
    print(f"  {'pair':>12} {'bank':>7}  {'archi':>7} {'Δ':>7} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0
    for (e, l) in pairs:
        bank_dv, br = bankrows[(e, l)]
        prob = pg.problem(PairUDPCirc(udp, e, l))
        algo = pg.algorithm(pg.cmaes(gen=300, force_bounds=True, ftol=1e-6, xtol=1e-6))
        archi = pg.archipelago()
        rng = np.random.default_rng(e * 100 + l)
        for k in range(8):
            pop = pg.population(prob, size=0)
            lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
            # seed 0: bank row (feasible); others: broad random incl long-tof slow arrivals
            if k == 0:
                bs = bank_to_seed(udp, br)
                bs = np.clip(bs[:12] if len(bs) >= 12 else np.concatenate([bs, np.zeros(12 - len(bs))]), lb, ub)
                pop.push_back(bs)
            for _ in range(24 - len(pop)):
                x = lb + rng.random(12) * (ub - lb)
                pop.push_back(x)
            archi.push_back(pg.island(algo=algo, pop=pop))
        archi.evolve(2); archi.wait()
        best = min(float(isl.get_population().champion_f[0]) for isl in archi)
        d = bank_dv - best if best < 1e5 else float("nan")
        hit = best < 1e5 and d > 50; wins += hit
        bs = f"{best:7.0f}" if best < 1e5 else "  FAIL"
        print(f"  ({e:>4},{l:>4}) {bank_dv:7.0f}  {bs} {d:+7.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-695] VERDICT: {wins}/{len(pairs)} expensive circular pairs beaten", flush=True)
    print("  >0 -> circular captures WERE never optimized -> the floored conclusion was a SOLVER BUG -> lever ALIVE", flush=True)


if __name__ == "__main__":
    main([(241, 50), (139, 31), (354, 305), (334, 312)])
