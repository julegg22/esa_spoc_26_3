"""E-687: DECISIVE test — is the bank's mid-burn (dv1, median 667) WASTE? Re-solve high-dv1 pairs
as clean 2-impulse (Lambert departure + coast + arrival, NO mid-burn) under the official BCP fitness.

Audit (2026-06-21): the fleet bank carries dv1 mean 620 (203/326 pairs >500). If 2-impulse re-solve
beats the bank's 3-impulse total -> the mid-burn is a suboptimal-basin artifact -> +86k lever (E-619's
'mid-burn killed' was true only for 3 winners). Uses best_lambert_seed (2-impulse) + lambert_dc (BCP
realize), on the most-mid-burn-heavy NON-circular pairs (lambert_dc works for eccentric arrivals).

Usage: python ch1_2impulse_test.py [n=12]
"""
import sys, json, math, numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_traj_lambert_dc import best_lambert_seed, lambert_dc
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def dv_from_mass(m):
    return -311.0 * 9.80665 * math.log((m + 500.0) / 5000.0) if m > 0 else float("nan")


def main(n=12):
    print("[E-687] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    L = 3.84405e8; Vunit = L / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    cands = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0: continue
        r = bank[i:i+21]; e, l = int(r[0]), int(r[1])
        dv1 = np.linalg.norm(r[13:16]) * Vunit
        tot = (np.linalg.norm(r[10:13]) + dv1/Vunit*0 + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
        # recompute total properly
        tot = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
        if eL[l] < 0.1:           # skip circular (lambert_dc narrow-window fails — separate issue)
            continue
        cands.append((dv1, e, l, tot))
    cands.sort(reverse=True)       # highest mid-burn first
    picks = cands[:n]
    print(f"[E-687] {len(cands)} non-circular bank pairs; testing {n} with the LARGEST mid-burn (dv1)", flush=True)
    print(f"  {'pair':>12} {'bank_tot':>8} {'bank_dv1':>8}  {'2imp_tot':>8} {'Δtot':>7} {'beats?':>7}", flush=True)
    wins = 0; tot_gain = 0.0
    for dv1, e, l, btot in picks:
        seed = best_lambert_seed(udp, e, l)
        if seed is None:
            print(f"  ({e:>4},{l:>4}) {btot:8.0f} {dv1:8.0f}  NO-SEED", flush=True); continue
        res = lambert_dc(udp, e, l, seed, max_nfev=80, verbose=False)
        if res is None:
            print(f"  ({e:>4},{l:>4}) {btot:8.0f} {dv1:8.0f}  DC-FAIL (lam {seed['total']:.0f})", flush=True); continue
        row, fit, cost = res
        if fit >= 0:
            print(f"  ({e:>4},{l:>4}) {btot:8.0f} {dv1:8.0f}  REJECTED", flush=True); continue
        s2dv = dv_from_mass(-fit)
        d = btot - s2dv
        hit = d > 50; wins += hit; tot_gain += max(d, 0)
        print(f"  ({e:>4},{l:>4}) {btot:8.0f} {dv1:8.0f}  {s2dv:8.0f} {d:+7.0f} {'YES' if hit else 'no':>7}", flush=True)
    print(f"\n[E-687] VERDICT: {wins}/{n} beaten by clean 2-impulse; mean Δtot={tot_gain/n:.0f} m/s", flush=True)
    print("  >0 -> mid-burn IS waste -> +86k lever real (scale 2-impulse re-solve fleet-wide)", flush=True)
    print("  ~0 -> mid-burn is needed (the 3-impulse is genuinely optimal) -> lever closes", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
