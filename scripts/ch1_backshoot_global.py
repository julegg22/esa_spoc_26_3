"""E-699: BACKWARD-SHOOTING + GLOBAL smooth search (the synthesis).
Forward targeting can't hit the narrow lunar radius+plane window to 384m/1e-6. Backward shooting makes
the ARRIVAL EXACT BY CONSTRUCTION (start ON the orbit via moon_orbit_state), and the global smooth
search handles the EARTH-side connection (forgiving: larger orbit, solve_departure_dv corrects).

Decision vector: [raan_m, argp_m, ea_m, dv2(3), t_arr, tof] -> start on the Moon orbit, retro-insert
(reverse LOI = -dv2), back-propagate tof to the Earth side; smooth penalty drives D onto the Earth
orbit. Objective |dv0|+|dv2|. Global CMA-ES restarts. OFFICIAL validation by forward udp.fitness.
"""
import sys, json, math, time
import numpy as np
import pygmo as pg
from scipy.optimize import minimize, least_squares
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, moon_orbit_state, state2earth, V, L, T
from esa_spoc_26.ch1_trajectory_solve import _back_state, _earth_inertial, solve_departure_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi


class UDPBack:
    def __init__(self, udp, idE, idL):
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aM, self.eM, self.iM = udp.moon_data[idL]

    def get_bounds(self):
        #     raan_m argp_m ea_m   dv2x dv2y dv2z  t_arr  tof
        return ([0, 0, 0, -1.2, -1.2, -1.2, 0.0, 0.5],
                [TWO_PI, TWO_PI, TWO_PI, 1.2, 1.2, 1.2, TWO_PI, 12.0])

    def _back(self, x):
        raan_m, argp_m, ea_m = x[0], x[1], x[2]; dv2 = x[3:6]; t_arr, tof = x[6], x[7]
        S = moon_orbit_state(self.aM, self.eM, self.iM, raan_m, argp_m, ea_m)   # EXACTLY on the orbit
        pre = [S[0], [S[1][0] - dv2[0], S[1][1] - dv2[1], S[1][2] - dv2[2]]]     # pre-insertion velocity
        D = _back_state(pre[0], pre[1], t_arr, tof)
        return S, dv2, t_arr, tof, D

    def fitness(self, x):
        try:
            S, dv2, t_arr, tof, D = self._back(x)
        except Exception:
            return [3e4]
        if D is None:
            return [2.5e4]
        d_state = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]
        try:
            el = state2earth(d_state)                       # (a,e,i) on the Earth side
            r_ef, _ = _earth_inertial(d_state); r = np.linalg.norm(r_ef)
        except Exception:
            return [2.5e4]
        dep = solve_departure_dv(d_state, self.aE, self.eE, self.iE)
        if dep is not None:                                 # FEASIBLE: real total dv
            _, dv0, _ = dep
            return [(np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V]
        # smooth UNCAPPED penalty: drive the Earth-side radius -> aE and inclination -> iE from anywhere
        miss = abs(r - self.aE) / 1000.0
        inc = abs(el[2] - self.iE) * 5000.0
        return [1.3e4 + miss + inc]


def official_row(udp, idE, idL, x):
    prob = UDPBack(udp, idE, idL)
    S, dv2, t_arr, tof, D = prob._back(x)
    if D is None:
        return None
    d_state = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]
    dep = solve_departure_dv(d_state, prob.aE, prob.eE, prob.iE)
    if dep is None:
        return None
    posvel0, dv0, _ = dep
    row = [idE, idL, 0, float(t_arr - tof), *posvel0[0], *posvel0[1], *np.asarray(dv0).tolist(),
           0.0, 0.0, 0.0, *np.asarray(dv2).tolist(), float(tof), 0.0]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    return row, (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V, -f


def solve_pair(udp, idE, idL, restarts=8, gen=200, seed0=0, verbose=False):
    prob = pg.problem(UDPBack(udp, idE, idL))
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-6, xtol=1e-6))
    best = None
    for rs in range(restarts):
        rng = np.random.default_rng(seed0 + 1009 * rs + idE * 7 + idL)
        pop = pg.population(prob, size=0)
        for _ in range(22):
            pop.push_back(lb + rng.random(8) * (ub - lb))
        pop = cma.evolve(pop)
        xb = pop.champion_x; fb = float(pop.champion_f[0])
        if fb < 1.25e4:
            res = minimize(lambda z: prob.fitness(z)[0], xb, method="Nelder-Mead",
                           options={"maxiter": 400, "fatol": 1e-3})
            if prob.fitness(res.x)[0] < fb:
                xb = res.x
            ov = official_row(udp, idE, idL, xb)
            if ov is not None and (best is None or ov[1] < best[1]):
                best = ov
                if verbose:
                    print(f"      rs{rs}: feas {fb:.0f} -> OFFICIAL VALID dv={ov[1]:.0f} mass={ov[2]:.0f}", flush=True)
            elif verbose:
                print(f"      rs{rs}: feas {fb:.0f}, official rejected", flush=True)
        elif verbose:
            print(f"      rs{rs}: infeasible {fb:.0f}", flush=True)
    return best


def main():
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    print("[E-699] init backward-shooting global solver ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    rows = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        rows.append((dv, e, l, eL[l]))
    rows.sort(reverse=True)
    print(f"[E-699] backward-global on {n} most-expensive pairs (arrival EXACT by construction)", flush=True)
    t0 = time.time(); wins = 0
    for dv, e, l, el in rows[:n]:
        print(f"  --- ({e},{l}) bank={dv:.0f} eL={el:.3f} ---", flush=True)
        res = solve_pair(udp, e, l, restarts=8, gen=200, verbose=True)
        if res is None:
            print(f"  ({e},{l}) bank={dv:.0f} -> FAIL [{time.time()-t0:.0f}s]", flush=True); continue
        d = dv - res[1]; hit = d > 30; wins += hit
        print(f"  ({e},{l}) bank={dv:.0f} -> OFFICIAL {res[1]:.0f} (Δ{d:+.0f}) {'BEATS' if hit else 'no'} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-699] VERDICT: {wins}/{n} beaten by backward-shooting global solver", flush=True)


if __name__ == "__main__":
    main()
