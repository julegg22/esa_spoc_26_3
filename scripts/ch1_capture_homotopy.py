"""E-749 probe #1 — CONTINUATION/HOMOTOPY capture solver for circular Moon orbits (the ch1 rank-2 lever).
Audit E-749: the +118k-kg gap is circular-orbit capture, method-floored at ~1139 m/s; eccentric orbits capture
cheaply but circular ones COLD-START-FAIL (E-682 best_dv=1e6, E-694 NO-PERI = convergence, not physics). Fix:
solve the circular target by CONTINUATION from a converged eccentric solution — override the Moon eccentricity eM
from ~0.35 down to the real (near-zero) value in steps, re-converging x each step (warm Nelder-Mead), tracking the
solution onto the razor-thin circular target instead of cold-starting it.
BINARY: if a circular pair reaches DV2<700 via homotopy (vs its bank ~1139) -> lever OPEN (cold-start was the wall);
if DV2 blows up / branch turns back as eM->0 -> circular capture is genuinely energy-floored.
Usage: python ch1_capture_homotopy.py [npairs=5]"""
import sys, json, time
import numpy as np
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from ch1_backshoot_ecc import UDPBackEcc, official_row
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
ROOT = "/home/julian/Projects/esa_spoc_26_3"
udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def solve(idE, idL, eM_over, x0=None, gen=250, pop=24):
    prob = UDPBackEcc(udp, idE, idL); prob.eM = eM_over
    if x0 is None:
        pgp = pg.problem(prob)
        algo = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True))
        P = pg.population(pgp, pop, seed=1)
        P = algo.evolve(P)
        return P.champion_x, float(P.champion_f[0])
    r = minimize(lambda z: prob.fitness(z)[0], x0, method="Nelder-Mead",
                 options={"maxiter": 600, "xatol": 1e-7, "fatol": 1e-4})
    return r.x, float(r.fun)


def dv2_of(x):
    return float(np.linalg.norm(x[3:6]) * V)


def main():
    npairs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    cand = []
    for i in range(len(bank) // 21):
        r = bank[i * 21:(i + 1) * 21]
        idE, idL = int(r[0]), int(r[1])
        if idE < 0:
            continue
        eM = udp.moon_data[idL][1]
        dv2 = float(np.linalg.norm(r[16:19]) * V)
        if eM < 0.05:                                            # circular target
            cand.append((dv2, idE, idL, eM))
    cand.sort(reverse=True)                                      # worst (highest dv2) circular captures first
    pairs = cand[:npairs]
    print(f"[E-749p1] {len(cand)} circular(eM<0.05) bank pairs; homotopy on {npairs} worst "
          f"(bank dv2 {pairs[0][0]:.0f}..{pairs[-1][0]:.0f} m/s)", flush=True)
    t0 = time.time(); wins = 0
    for bank_dv2, idE, idL, eM in pairs:
        target = max(eM, 0.003)
        schedule = np.linspace(0.35, target, 12)
        x = None; ok = True
        for k, em in enumerate(schedule):
            x, f = solve(idE, idL, em, x0=x, gen=250 if k == 0 else 0)
            if f > 1.2e4:                                        # left the feasible regime
                # one CMA re-seed at this eM to recover the branch
                x, f = solve(idE, idL, em, x0=None, gen=150)
                if f > 1.2e4:
                    ok = False; break
        if not ok:
            print(f"[E-749p1] ({idE},{idL}) eM={eM:.3f} bank_dv2={bank_dv2:.0f}: homotopy LOST branch (f={f:.0f}) "
                  f"[{time.time()-t0:.0f}s]", flush=True); continue
        # validate on the REAL target (official udp.fitness via official_row)
        res = official_row(udp, idE, idL, x)
        valid = isinstance(res, (list, tuple)) and len(res) == 21
        fin_dv2 = dv2_of(x); tot = f
        flag = "<<WIN" if fin_dv2 < 700 else ""
        print(f"[E-749p1] ({idE},{idL}) eM={eM:.3f} bank_dv2={bank_dv2:.0f} -> homotopy dv2={fin_dv2:.0f} "
              f"tot={tot:.0f} valid_row={valid} {flag} [{time.time()-t0:.0f}s]", flush=True)
        if fin_dv2 < 700:
            wins += 1
    print(f"[E-749p1] DONE: {wins}/{npairs} circular pairs reached dv2<700 via homotopy. "
          f"{'LEVER OPEN (cold-start was the wall)' if wins else 'no win -> circular capture energy-floored OR homotopy needs work'} "
          f"[{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
