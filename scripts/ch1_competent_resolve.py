"""E-689: is the bank at OUR-tooling's per-pair floor, or can a COMPETENT local optimizer (all DOF
free, gradient-ish) descend below it from the feasible bank seed? (Tests A0/A5: weak-solver floor.)

For each high-total bank pair, seed the full continuous DOF from the bank and run scipy.minimize
(Powell, robust derivative-free local) on [raan_e,argp_e,ea_e,t0,dv0(3),dv1(3),T1,T2] minimizing
total dv, dv2 solved by solve_arrival_dv (works for circular too). If it descends > 50 m/s below
bank on many pairs -> our heuristic solvers left the floor unreached -> a competent NLP is the lever.

Usage: python ch1_competent_resolve.py [n=10]
"""
import sys, json, math, numpy as np
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, earth_orbit_state, propagate, V
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"
PEN = 1e6


def main(n=10):
    print("[E-689] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    rows = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        tot = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        rows.append((tot, r))
    rows.sort(reverse=True)
    picks = rows[:n]
    print(f"[E-689] competent local re-solve (Powell, all DOF) from bank seed on {n} highest-dv pairs", flush=True)
    print(f"  {'pair':>12} {'bank_tot':>8}  {'resolved':>8} {'Δ':>7} {'beats?':>7}", flush=True)
    wins = 0; gain = 0.0
    for btot, r in picks:
        e, l = int(r[0]), int(r[1])
        aE, eE, iE = udp.earth_data[e]; aM, eM, iM = udp.moon_data[l]
        # recover the bank's departure angles from its stored state via earth_orbit_state inverse is hard;
        # instead optimize raan_e,argp_e,ea_e fresh but seed near bank by matching the stored pv0 loosely.
        # Decision vector: [raan_e, argp_e, ea_e, t0, dv0(3), dv1(3), T1, T2]
        x0 = np.array([0.0, 0.0, 0.0, r[3], *r[10:13], *r[13:16], r[19], r[20]])

        def total(x):
            raan_e, argp_e, ea_e, t0 = x[0], x[1], x[2], x[3]
            dv0 = x[4:7]; dv1 = x[7:10]; T1, T2 = x[10], x[11]
            if T1 < 0.02 or T2 < 0.0:
                return PEN
            try:
                pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_e)
                pv1 = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]], [T1, T2])
            except Exception:
                return PEN
            if len(pv1) == 0:
                return PEN
            a2 = solve_arrival_dv(pv1, aM, eM, iM)
            if a2 is None:
                return PEN
            return (np.linalg.norm(dv0) + np.linalg.norm(dv1) + np.linalg.norm(a2[0])) * V
        # the bank seed uses a specific pv0; our x0 raan/argp/ea=0 won't match it, so the seed total
        # will differ. Run from a few angle seeds to give the local optimizer a feasible start.
        best = None
        for seed_ang in range(6):
            xs = x0.copy()
            xs[0] = seed_ang * math.pi / 3
            xs[2] = (seed_ang % 3) * 2 * math.pi / 3
            res = minimize(total, xs, method="Powell", options={"maxiter": 4000, "xtol": 1e-6, "ftol": 1e-4})
            if res.fun < PEN and (best is None or res.fun < best):
                best = float(res.fun)
        if best is None:
            print(f"  ({e:>4},{l:>4}) {btot:8.0f}  {'INFEAS':>8}", flush=True); continue
        d = btot - best; hit = d > 50; wins += hit; gain += max(d, 0)
        print(f"  ({e:>4},{l:>4}) {btot:8.0f}  {best:8.0f} {d:+7.0f} {'YES' if hit else 'no':>7}", flush=True)
    print(f"\n[E-689] VERDICT: {wins}/{n} beaten by competent local re-solve; mean Δ={gain/n:.0f} m/s", flush=True)
    print("  many YES -> our heuristic solvers were the bottleneck -> competent NLP is the +lever", flush=True)
    print("  ~all no -> bank at the real per-pair floor -> the gap is NOT per-pair (assignment/fill/structure)", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
