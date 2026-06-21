"""E-681: DECISIVE test of the trajectory audit flaw — does the full 12-DOF BCP-direct UDP reach
ΔV well below the bank's ~4324 m/s (toward the 3940 Hohmann floor and the ~2734 leader-implied)?

Audit (E-681): the bank (263k kg, median ΔV 4324 m/s, 79% of pairs ABOVE the 3940 two-body Hohmann
floor) was built with the WEAK patched-conic path; the full BCP-direct UDP (ch1_pair_udp.py, free
12-DOF, real heyoka BCP propagator) EXISTS but was never deployed at fleet scale. The "can't get below
3850 / need WSB" verdict came from a RESTRICTED refinement. If the full UDP lands sub-3940 on the
high-ΔV pairs → the lever is alive (rank 6→5→3), same shape as matching's solver-bound flaw.

Picks the N highest-ΔV active bank pairs, runs sade on the full UDP seeded from bank, reports
bank ΔV/mass → UDP ΔV/mass (and ΔT for the time-discount caveat). Usage: python ch1_udp_decisive_test.py [N=10]
"""
import sys, json, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_pair_udp import PairUDP, multi_seed_pop, chromosome_to_row, mass_from_row
ROOT = "/home/julian/Projects/esa_spoc_26_3"
ISP_G0 = 311 * 9.80665


def dv_from_mass(m):
    return -ISP_G0 * np.log((m + 500.0) / 5000.0) if m > 0 else float('nan')


def main(N=10):
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    Vunit = 3.84405e8 / 3.7567696752e5
    rows = {}
    dvs = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        dv_si = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
        rows[(e, l)] = r; dvs.append((dv_si, e, l))
    dvs.sort(reverse=True)                      # highest-dV pairs = most room
    picks = dvs[:N]
    print(f"[E-681] testing {N} HIGHEST-ΔV bank pairs with the full 12-DOF BCP-direct UDP (sade)", flush=True)
    print(f"  {'pair':>14} {'bank_dV':>8} {'bank_kg':>8}  {'UDP_dV':>8} {'UDP_kg':>8}  {'Δkg':>7} {'<3940?':>7}", flush=True)
    wins = 0; sub_floor = 0; tot_gain = 0.0; t0 = time.time()
    for bank_dv, e, l in picks:
        br = rows[(e, l)]; bank_m = mass_from_row(udp, br)
        prob = pg.problem(PairUDP(udp, e, l))
        algo = pg.algorithm(pg.sade(gen=150, ftol=0.0, xtol=0.0))
        pop = multi_seed_pop(prob, udp, e, l, pop_size=30, bank_row=br)
        pop = algo.evolve(pop)
        if pop.champion_f[0] > 1e5:
            print(f"  ({e:>4},{l:>4}): bank dV={bank_dv:.0f} kg={bank_m:.0f}  -> UDP FAIL", flush=True)
            continue
        row = chromosome_to_row(udp, pop.champion_x, e, l)
        udp_m = mass_from_row(udp, row) if row else 0.0
        udp_dv = dv_from_mass(udp_m)
        gain = udp_m - bank_m
        if gain > 1: wins += 1
        if udp_dv < 3940: sub_floor += 1
        tot_gain += max(gain, 0)
        print(f"  ({e:>4},{l:>4}): {bank_dv:8.0f} {bank_m:8.0f}  {udp_dv:8.0f} {udp_m:8.0f}  {gain:+7.0f} "
              f"{'YES' if udp_dv<3940 else 'no':>7}  [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-681] VERDICT: {wins}/{N} improved, {sub_floor}/{N} reached SUB-3940 (impulsive floor), "
          f"total +{tot_gain:.0f} kg on these {N} pairs", flush=True)
    print(f"  If sub_floor is high → the full UDP breaks the ~3850 cap → FLEET SWEEP is the rank-6→3 lever.", flush=True)
    print(f"  If UDP≈bank → the UDP also caps here → audit flaw NOT confirmed; report honestly.", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
