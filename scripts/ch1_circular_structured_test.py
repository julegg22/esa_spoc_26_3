"""E-684: does the STRUCTURED Lambert+DC solver beat the bank on the EXPENSIVE circular captures?

Both black-box probes (E-682/683) returned PENALTY on circular pairs — the narrow capture window
needs the structured solver. The bank's circular captures are heterogeneous (dv 1955-6617), NOT
inclination-driven. This re-runs the structured solver (best_lambert_seed -> lambert_dc, the tool
that BUILT the bank) FRESH on the most-expensive circular (eL<0.1, dv>=4800) bank pairs and compares.

DECISIVE: structured dv < bank dv substantially?
  YES -> our bank left circular captures suboptimal -> per-pair re-solve lever (tractable, +headroom).
  NO  -> bank at the structured per-pair floor -> expensive circular pairs are intrinsically
         expensive -> lever is RE-ASSIGNMENT (build true dv-cost matrix), not per-pair re-solve.

Usage: python ch1_circular_structured_test.py [n_pairs=6]
"""
import sys, json, time, math
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_traj_lambert_dc import best_lambert_seed, lambert_dc
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def dv_from_mass(m):
    return -311.0 * 9.80665 * math.log((m + 500.0) / 5000.0) if m > 0 else float("nan")


def main(n_pairs=6):
    print("[E-684] init: heyoka BCP + orbits ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    Vunit = 3.84405e8 / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    cands = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        if eL[l] >= 0.1:
            continue
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
        if dv < 4800:
            continue
        cands.append((dv, e, l))
    cands.sort(reverse=True)
    picks = cands[:n_pairs]
    print(f"[E-684] {len(cands)} expensive circular(eL<0.1,dv>=4800) bank pairs; structured re-solve on {n_pairs}", flush=True)
    print(f"  {'pair':>12} {'bank_dv':>8}  {'struct_dv':>9} {'Δdv':>7} {'beats?':>7} [{'t':>5}]", flush=True)
    t0 = time.time(); wins = 0; tot = 0.0
    for bank_dv, e, l in picks:
        ts = time.time()
        try:
            seed = best_lambert_seed(udp, e, l)
            if seed is None:
                print(f"  ({e:>4},{l:>4}) {bank_dv:8.0f}  {'NO-SEED':>9} {'':>7} {'no':>7} [{time.time()-t0:.0f}s]", flush=True)
                continue
            res = lambert_dc(udp, e, l, seed, max_nfev=60, verbose=False)
        except Exception as ex:
            print(f"  ({e:>4},{l:>4}) ERROR {ex}", flush=True)
            continue
        if res is None:
            print(f"  ({e:>4},{l:>4}) {bank_dv:8.0f}  {'DC-FAIL':>9} (lambert seed dv={seed['total']:.0f}) {'no':>7} [{time.time()-t0:.0f}s]", flush=True)
            continue
        row, fit, cost = res
        mass = -fit if fit < 0 else 0.0
        sdv = dv_from_mass(mass) if mass > 0 else float("nan")
        d = bank_dv - sdv if mass > 0 else float("nan")
        hit = (mass > 0) and (d > 50)
        wins += hit; tot += max(d, 0) if mass > 0 else 0
        tag = "YES" if hit else ("rej" if mass <= 0 else "no")
        print(f"  ({e:>4},{l:>4}) {bank_dv:8.0f}  {sdv:9.0f} {d:+7.0f} {tag:>7} [{time.time()-t0:.0f}s] (seed {seed['total']:.0f})", flush=True)
    print(f"\n[E-684] VERDICT: {wins}/{n_pairs} expensive circular pairs beaten by the structured solver; mean Δdv={tot/n_pairs:.0f}", flush=True)
    print("  >0 -> per-pair re-solve headroom on circular captures (tractable lever, guard-bank + scale)", flush=True)
    print("  0  -> bank at structured per-pair floor -> expensive circular pairs intrinsically costly -> lever is RE-ASSIGNMENT", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
