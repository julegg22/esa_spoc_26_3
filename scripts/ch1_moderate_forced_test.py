"""E-754 decisive test — FORCE moderate TOF and measure the TOTAL (does slow arrival help or does dv0 offset it?).
E-754 measured circular capture 1138 = our fast arrival (v_inf 1553), floor 609; predicted moderate-TOF (30-60d)
-> capture ~620 -> +60k. BUT correction: UDPBackEcc tof bound [0.5,12]=2.2-52d ALREADY allows moderate TOF and the
ecc fleet found little. So either the cheap-capture solutions don't exist (departure dv0 rises to offset) OR the
cold-start CMA misses the narrow moderate-TOF basin. THIS forces tof into [8.0,13.8]=35-60d (a moderate-only UDP)
+ heavy restarts, and compares the best TOTAL to the bank. BINARY: forced-moderate total << bank -> basin exists,
CMA missed it (SEED the fleet there, +60k real). forced-moderate total >= bank -> dv0 offsets, lever is smaller/closed.
Usage: python ch1_moderate_forced_test.py [npairs=3]"""
import sys, json, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from ch1_backshoot_ecc import UDPBackEcc, official_row
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
ROOT = "/home/julian/Projects/esa_spoc_26_3"
udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
TWO_PI = 2 * np.pi


class UDPModerate(UDPBackEcc):
    def get_bounds(self):
        # force tof into the MODERATE band 8.0-13.8 normalized = ~35-60 days (vs default 0.5-12 = 2.2-52d)
        return ([0, 0, 0, -1.2, -1.2, -1.2, 0.0, 8.0],
                [TWO_PI, TWO_PI, TWO_PI, 1.2, 1.2, 1.2, TWO_PI, 13.8])


def solve(prob_cls, idE, idL, restarts=20, gen=250):
    prob = pg.problem(prob_cls(udp, idE, idL))
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-7))
    best = None
    rng = np.random.default_rng(idE * 7 + idL)
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    for _ in range(restarts):
        pop = pg.population(prob, 0)
        for _i in range(20):
            pop.push_back(lb + rng.random(8) * (ub - lb))
        pop = cma.evolve(pop)
        f = float(pop.champion_f[0])
        if best is None or f < best[0]:
            best = (f, pop.champion_x)
    return best


def main():
    npairs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    md = np.array(udp.moon_data)
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    N = len(bank) // 21
    cand = []
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0 or md[int(r[1]), 1] >= 0.05:
            continue
        tot = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        d2 = np.linalg.norm(r[16:19]) * V
        cand.append((tot, d2, int(r[0]), int(r[1])))
    cand.sort(reverse=True)
    print(f"[E-754t] FORCED-moderate-TOF (35-60d) test on {npairs} worst circular pairs vs bank", flush=True)
    t0 = time.time(); wins = 0
    for bank_tot, bank_d2, idE, idL in cand[:npairs]:
        b = solve(UDPModerate, idE, idL, restarts=20, gen=250)
        if b is None:
            print(f"[E-754t] ({idE},{idL}) bank {bank_tot:.0f}: forced-moderate NO SOLUTION [{time.time()-t0:.0f}s]", flush=True); continue
        f, x = b
        valid = f < 1.3e4
        moderate_tot = f if valid else None
        tof_d = x[7] * 4.348
        if valid and f < bank_tot - 100:
            wins += 1; flag = "<<WIN (basin exists, CMA missed it)"
        else:
            flag = "(no gain - dv0 offsets OR infeasible)"
        print(f"[E-754t] ({idE},{idL}) bank total {bank_tot:.0f} (dv2 {bank_d2:.0f}) -> "
              f"forced-moderate total {f:.0f} @ tof {tof_d:.0f}d valid={valid} {flag} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-754t] DONE: {wins}/{npairs} improved >100 m/s with forced-moderate TOF. "
          f"{'BASIN EXISTS -> seed the fleet, +60k REAL' if wins else 'NO -> moderate-TOF dv0 offsets the capture saving; +60k was over-optimistic, re-scope'} "
          f"[{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
