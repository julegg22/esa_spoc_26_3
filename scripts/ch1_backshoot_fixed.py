"""E-696: backward-shooting with the H-010 FIX (the bug my E-693 test never applied).
solve_transfer_back's residual was UNDER-DETERMINED: [(|r_ef|-aE)/L] = 1 eq, 5 unknowns -> the
backward trajectory hit the Earth RADIUS but with arbitrary (often retrograde) e,i -> huge dv0.
FIX: match the FULL (a,e,i) via state2earth (3 eqs), minimize dv2 in the free DOF. Backward shooting
starts ON the LLO with a small retro-burn = the MINIMUM-ENERGY capture by construction (dv2~875),
which is exactly the thin slow-arrival manifold forward solvers + random seeds can't reach.

DECISIVE on the expensive circular pairs (bank dv2 2434, floor ~875): does fixed backward-shooting
realize the cheap capture and beat the bank?
"""
import sys, json, math, time
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, moon_orbit_state, state2earth, V, T, L
from esa_spoc_26.ch1_trajectory_solve import _back_state, _earth_inertial, solve_departure_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def solve_back_fixed(udp, idE, idL, n_seed=16, tof_grid=(3.0, 4.0, 5.0, 6.0, 8.0)):
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    rng = np.random.default_rng(idE * 131 + idL)
    for tof_d in tof_grid:
        tof = tof_d * 86400.0 / T
        for _k in range(n_seed):
            nuM = rng.uniform(0, 2 * np.pi); OmM = rng.uniform(0, 2 * np.pi)
            arr = moon_orbit_state(aL, eL, iL, OmM, 0.0, nuM)
            _, vmf = _earth_inertial(arr)            # rough scale for retro seed
            dv2_seed = np.array([0.0, 0.0, 0.0])

            def resid(p, _OmM=OmM, _tof=tof):
                nu, t_arr = p[0], p[1]; dv2 = p[2:5]
                a = moon_orbit_state(aL, eL, iL, _OmM, 0.0, nu)
                S = [a[0], [a[1][0] - dv2[0], a[1][1] - dv2[1], a[1][2] - dv2[2]]]
                D = _back_state(S[0], S[1], t_arr, _tof)
                if D is None:
                    return [10.0, 10.0, 10.0, 10.0]
                el = state2earth([[D[0], D[1], D[2]], [D[3], D[4], D[5]]])
                # H-010 FIX: match full (a,e,i); 4th residual lightly minimizes |dv2| (drives min-energy)
                return [(el[0] - aE) / L, el[1] - eE, el[2] - iE, 0.05 * np.linalg.norm(dv2)]

            x0 = np.array([nuM, 0.0, *dv2_seed])
            sol = least_squares(resid, x0, method="trf", xtol=1e-12, max_nfev=120)
            nu, t_arr = sol.x[0], sol.x[1]; dv2 = sol.x[2:5]
            arr = moon_orbit_state(aL, eL, iL, OmM, 0.0, nu)
            S = [arr[0], [arr[1][0] - dv2[0], arr[1][1] - dv2[1], arr[1][2] - dv2[2]]]
            D = _back_state(S[0], S[1], t_arr, tof)
            if D is None:
                continue
            d_state = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]
            dep = solve_departure_dv(d_state, aE, eE, iE)
            if dep is None:
                continue
            posvel0, dv0, _ = dep
            row = [idE, idL, 0, t_arr - tof, *posvel0[0], *posvel0[1],
                   *dv0, 0.0, 0.0, 0.0, *np.asarray(dv2).tolist(), float(tof), 0.0]
            f = udp.fitness(row)[0]
            if f < 0:
                dvms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
                if best is None or dvms < best[0]:
                    best = (dvms, -f, row)
    return best


def main(pairs):
    print("[E-696] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    br = {}
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        br[(int(r[0]), int(r[1]))] = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
    print(f"  {'pair':>12} {'bank_dv':>7}  {'bsfix_dv':>8} {'Δ':>7} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0
    for (e, l) in pairs:
        bd = br[(e, l)]
        res = solve_back_fixed(udp, e, l)
        if res is None:
            print(f"  ({e:>4},{l:>4}) {bd:7.0f}  {'FAIL':>8} [{time.time()-t0:.0f}s]", flush=True); continue
        d = bd - res[0]; hit = d > 50; wins += hit
        print(f"  ({e:>4},{l:>4}) {bd:7.0f}  {res[0]:8.0f} {d:+7.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-696] VERDICT: {wins}/{len(pairs)} beaten by H-010-FIXED backward shooting", flush=True)
    print("  >0 -> the H-010 bug was the culprit -> minimum-energy capture realized -> +117k LEVER ALIVE", flush=True)


if __name__ == "__main__":
    main([(241, 50), (139, 31), (354, 305), (334, 312), (244, 105), (249, 22)])
