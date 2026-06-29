"""E-754 probe — moderate-TOF capture for circular pairs (the reopened lever). E-754 measured: circular capture
1138 m/s is our FAST ARRIVAL (v_inf~1553); the standard periapsis floor is ~609, reachable with moderate-TOF
(30-60d) slow arrival; cargo cap non-binding at 50d -> +~60k kg. The PairUDP TOF cap (~43d) + E-682's cold-start
convergence failure closed this. solve_transfer_back already backward-shoots with a low-v_inf seed; just extend
its tof_grid into the moderate band on the worst circular pairs and see if DV2/total drops.
DECISIVE: does any circular pair reach total << bank (toward ~3300 m/s, capture toward ~620) at TOF 20-65d?
Usage: python ch1_moderate_tof_probe.py [npairs=6]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
from esa_spoc_26.ch1_trajectory_solve import solve_transfer_back
ROOT = "/home/julian/Projects/esa_spoc_26_3"
udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def main():
    npairs = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    md = np.array(udp.moon_data)
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    N = len(bank) // 21
    cand = []
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0:
            continue
        idE, idL = int(r[0]), int(r[1])
        if md[idL, 1] >= 0.05:                                   # circular only
            continue
        d0 = np.linalg.norm(r[10:13]) * V; d2 = np.linalg.norm(r[16:19]) * V
        cand.append((d0 + d2, d2, idE, idL))
    cand.sort(reverse=True)
    pairs = cand[:npairs]
    print(f"[E-754p] {len(cand)} circular pairs; probing {npairs} worst. Short-TOF bank vs moderate-TOF re-solve.", flush=True)
    print(f"[E-754p] (bank circular DV2 mean ~1138; periapsis floor ~609; target total ~3300)", flush=True)
    t0 = time.time(); wins = 0
    for bank_tot, bank_dv2, idE, idL in pairs:
        best = {}
        for label, grid in [("MODERATE", (40.0, 55.0))]:        # light: just the moderate band, vs bank
            res = solve_transfer_back(udp, idE, idL, n_seed=6, tof_grid=grid)
            if res[0] is not None:
                row, mass, dv_ms, dt_d = res
                best[label] = (dv_ms, mass, dt_d)
            else:
                best[label] = None
        s = None; m = best.get("MODERATE")
        ss = "bank-band: (skipped)"
        if m:
            flag = "<<WIN" if m[0] < bank_tot - 200 else ""
            ms = f"MODERATE total {m[0]:.0f} m/s @{m[2]:.1f}d mass {m[1]:.0f}"
            if m[0] < bank_tot - 200:
                wins += 1
        else:
            ms = "MODERATE: no soln (convergence?)"; flag = ""
        print(f"[E-754p] ({idE},{idL}) bank total {bank_tot:.0f} (dv2 {bank_dv2:.0f}) | {ss} | {ms} {flag} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-754p] DONE: {wins}/{npairs} circular pairs improved >200 m/s via moderate-TOF. "
          f"{'LEVER CONFIRMED -> build full-fleet moderate-TOF re-solve (+~60k)' if wins else 'no win -> check seeding/geometry'} "
          f"[{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
