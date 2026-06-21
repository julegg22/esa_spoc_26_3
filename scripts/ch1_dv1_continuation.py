"""E-688: DECISIVE continuation test — is the bank's mid-burn (dv1) a weak-solver CRUTCH or optimal?

Start from the FEASIBLE bank trajectory (already on the LLO), homotopically scale dv1 -> 0 while
re-converging dv0 (DC) to keep the endpoint on the LLO; read total dv at each alpha. Feasible start
avoids the cold-start failures that broke E-682/683/686.
  total DROPS as dv1->0  -> mid-burn is a CRUTCH -> +86-100k lever (clean 2-impulse floor reachable).
  total RISES            -> mid-burn is genuinely optimal -> lever closes.

Usage: python ch1_dv1_continuation.py [n=10]
"""
import sys, json, math, numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, propagate, V
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main(n=10):
    print("[E-688] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    rows = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        dv1m = np.linalg.norm(r[13:16]) * V
        rows.append((dv1m, r))
    rows.sort(reverse=True)
    picks = rows[:n]
    print(f"[E-688] continuation on {n} highest-mid-burn bank pairs (dv1->0, re-converge dv0)", flush=True)
    print(f"  {'pair':>12} {'bank_tot':>8} {'dv1':>6} | total at alpha=  1.0   0.75   0.5   0.25   0.0   {'verdict':>9}", flush=True)
    improved = 0
    for dv1m, r in picks:
        e, l = int(r[0]), int(r[1])
        aM, eM, iM = udp.moon_data[l]
        t0 = r[3]
        pv0 = [list(r[4:7]), list(r[7:10])]
        dv0_b = np.array(r[10:13]); dv1_b = np.array(r[13:16]); dv2_b = np.array(r[16:19])
        T1, T2 = r[19], r[20]
        bank_tot = (np.linalg.norm(dv0_b) + np.linalg.norm(dv1_b) + np.linalg.norm(dv2_b)) * V
        pv1_b = propagate(pv0, t0, [dv0_b.tolist(), dv1_b.tolist(), [0, 0, 0]], [T1, T2])
        if len(pv1_b) == 0:
            print(f"  ({e:>4},{l:>4}) bank not reproducible", flush=True); continue
        target = np.array(pv1_b[0])
        dv0 = dv0_b.copy(); totals = []
        for alpha in (1.0, 0.75, 0.5, 0.25, 0.0):
            dv1 = alpha * dv1_b

            def resid(x):
                pv1 = propagate(pv0, t0, [x.tolist(), dv1.tolist(), [0, 0, 0]], [T1, T2])
                if len(pv1) == 0:
                    return np.array([20.0, 20.0, 20.0])
                return np.array(pv1[0]) - target
            sol = least_squares(resid, dv0, method="trf", xtol=1e-12, max_nfev=80)
            dv0 = sol.x
            pv1 = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]], [T1, T2])
            if len(pv1) == 0:
                totals.append(None); continue
            a2 = solve_arrival_dv(pv1, aM, eM, iM)
            if a2 is None:
                totals.append(None); continue
            dv2 = a2[0]
            totals.append((np.linalg.norm(dv0) + np.linalg.norm(dv1) + np.linalg.norm(dv2)) * V)
        ts = "  ".join(f"{t:6.0f}" if t is not None else "  FAIL" for t in totals)
        final = totals[-1]
        verdict = "CRUTCH" if (final is not None and final < bank_tot - 50) else ("optimal" if final is not None else "infeas")
        if verdict == "CRUTCH":
            improved += 1
        print(f"  ({e:>4},{l:>4}) {bank_tot:8.0f} {dv1m:6.0f} | {ts}   {verdict:>9}", flush=True)
    print(f"\n[E-688] VERDICT: {improved}/{n} pairs improve as dv1->0 (mid-burn is a CRUTCH)", flush=True)
    print("  many CRUTCH -> +86-100k lever real -> build the clean-2-impulse fleet re-solve", flush=True)
    print("  ~all optimal -> mid-burn needed -> lever closes, gap is elsewhere", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
