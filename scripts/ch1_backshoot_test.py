"""E-693: TEST backward-shooting (solve_transfer_back) on the expensive bank pairs.
Backward shooting starts ON the Moon orbit (tangential capture by construction, small dv2) and
shoots back to Earth -> realizes the cheap tangential capture the 9 forward solvers could not.
DECISIVE: does it beat the bank's per-pair total?"""
import sys, json, math, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_trajectory_solve import solve_transfer_back
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main(n=8):
    print("[E-693] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]; V = 3.84405e8 / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    rows = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        m = math.exp(-dv / 3050.0) * 5000 - 500
        rows.append((dv, e, l, m, eL[l]))
    rows.sort(reverse=True)
    picks = rows[:n]
    print(f"[E-693] backward-shooting on {n} most-expensive bank pairs (tangential capture by construction)", flush=True)
    print(f"  {'pair':>12} {'eL':>5} {'bank_dv':>7} {'bank_kg':>7}  {'bs_dv':>7} {'bs_kg':>7} {'Δkg':>7} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0; tot_gain = 0.0
    for bank_dv, e, l, bank_m, el in picks:
        res = solve_transfer_back(udp, e, l, n_seed=12, tof_grid=(3.0, 5.0, 8.0, 12.0))
        if res is None or res[0] is None:
            print(f"  ({e:>4},{l:>4}) {el:5.2f} {bank_dv:7.0f} {bank_m:7.0f}  {'FAIL':>7} [{time.time()-t0:.0f}s]", flush=True)
            continue
        row, mass, dvms, dt = res
        gain = mass - bank_m; hit = gain > 5; wins += hit; tot_gain += max(gain, 0)
        print(f"  ({e:>4},{l:>4}) {el:5.2f} {bank_dv:7.0f} {bank_m:7.0f}  {dvms:7.0f} {mass:7.0f} {gain:+7.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-693] VERDICT: {wins}/{n} pairs beaten by backward-shooting; total +{tot_gain:.0f} kg on these", flush=True)
    print("  >0 -> the tangential capture IS realizable backward -> the lever, scale fleet (est +50-100k)", flush=True)
    print("  0  -> backward shooting also can't beat bank -> per-pair truly floored, gap is elsewhere", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
