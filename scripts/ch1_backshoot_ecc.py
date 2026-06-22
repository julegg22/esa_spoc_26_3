"""E-701: backward-shooting solver with the CORRECT eccentric departure solver.
Decisive test of the hypothesis: the only thing blocking official-valid sub-bank captures was the
circular-only solve_departure_dv, not the precision/corrector. With the eccentric mirror, the feasible
regime (radius in [a_e(1-e_e), a_e(1+e_e)]) opens and CMA should find official-valid solutions directly."""
import sys, json, math, time
import numpy as np
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, moon_orbit_state, state2earth, V, L
from esa_spoc_26.ch1_trajectory_solve import _back_state, _earth_inertial
from ch1_departure_ecc import solve_departure_dv_ecc
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi


class UDPBackEcc:
    def __init__(self, udp, idE, idL):
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aM, self.eM, self.iM = udp.moon_data[idL]

    def get_bounds(self):
        return ([0, 0, 0, -1.2, -1.2, -1.2, 0.0, 0.5],
                [TWO_PI, TWO_PI, TWO_PI, 1.2, 1.2, 1.2, TWO_PI, 12.0])

    def _back(self, x):
        raan_m, argp_m, ea_m = x[0], x[1], x[2]; dv2 = x[3:6]; t_arr, tof = x[6], x[7]
        S = moon_orbit_state(self.aM, self.eM, self.iM, raan_m, argp_m, ea_m)
        pre = [S[0], [S[1][0] - dv2[0], S[1][1] - dv2[1], S[1][2] - dv2[2]]]
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
        dep = solve_departure_dv_ecc(d_state, self.aE, self.eE, self.iE)
        if dep is not None:
            _, dv0, _ = dep
            return [(np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V]
        # smooth penalty: drive the departure radius into the orbit's r-window [a(1-e),a(1+e)]
        try:
            r_ef, _ = _earth_inertial(d_state); r = np.linalg.norm(r_ef)
        except Exception:
            return [2.5e4]
        r_min, r_max = self.aE * (1 - self.eE), self.aE * (1 + self.eE)
        if r < r_min:
            miss = (r_min - r) / 1000.0
        elif r > r_max:
            miss = (r - r_max) / 1000.0
        else:
            miss = 0.0
        return [1.3e4 + miss]


def official_row(udp, idE, idL, x):
    prob = UDPBackEcc(udp, idE, idL)
    S, dv2, t_arr, tof, D = prob._back(x)
    if D is None:
        return None
    d_state = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]
    dep = solve_departure_dv_ecc(d_state, prob.aE, prob.eE, prob.iE)
    if dep is None:
        return None
    posvel0, dv0, _ = dep
    row = [idE, idL, 0, float(t_arr - tof), *posvel0[0], *posvel0[1], *np.asarray(dv0).tolist(),
           0.0, 0.0, 0.0, *np.asarray(dv2).tolist(), float(tof), 0.0]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None, f
    return row, (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V, -f


def solve_pair(udp, idE, idL, restarts=10, gen=250, seed0=0, verbose=False):
    prob = pg.problem(UDPBackEcc(udp, idE, idL))
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-7, xtol=1e-7))
    best = None
    for rs in range(restarts):
        rng = np.random.default_rng(seed0 + 1009 * rs + idE * 7 + idL)
        pop = pg.population(prob, size=0)
        for _ in range(24):
            pop.push_back(lb + rng.random(8) * (ub - lb))
        pop = cma.evolve(pop)
        xb = pop.champion_x; fb = float(pop.champion_f[0])
        if fb < 1.3e4:                                    # feasible regime reached
            res = minimize(lambda z: prob.fitness(z)[0], xb, method="Nelder-Mead",
                           options={"maxiter": 400, "fatol": 1e-3})
            if prob.fitness(res.x)[0] < fb:
                xb = res.x; fb = prob.fitness(res.x)[0]
            ov = official_row(udp, idE, idL, xb)
            if ov is not None and ov[0] is not None and (best is None or ov[1] < best[1]):
                best = ov
                if verbose:
                    print(f"      rs{rs}: feas {fb:.0f} -> OFFICIAL VALID dv={ov[1]:.0f} mass={ov[2]:.0f}", flush=True)
            elif verbose:
                rej = "off-rej f=%.2e" % ov[1] if ov is not None else "dep-None"
                print(f"      rs{rs}: feas {fb:.0f}, {rej}", flush=True)
        elif verbose:
            print(f"      rs{rs}: infeasible {fb:.0f} (penalty)", flush=True)
    return best


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print("[E-701] backshoot-ECC: eccentric departure solver (the real fix)", flush=True)
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
    print(f"[E-701] {n} most-expensive pairs (arrival exact; departure eccentric-aware)", flush=True)
    t0 = time.time(); wins = 0
    for dv, e, l, el in rows[:n]:
        print(f"  --- ({e},{l}) bank={dv:.0f} eL={el:.3f} eE={udp.earth_data[e,1]:.2e} ---", flush=True)
        res = solve_pair(udp, e, l, restarts=10, gen=250, verbose=True)
        if res is None:
            print(f"  ({e},{l}) bank={dv:.0f} -> FAIL [{time.time()-t0:.0f}s]", flush=True); continue
        d = dv - res[1]; hit = d > 30; wins += hit
        print(f"  ({e},{l}) bank={dv:.0f} -> OFFICIAL {res[1]:.0f} (Δ{d:+.0f}) {'BEATS' if hit else 'no'} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-701] VERDICT: {wins}/{n} official-valid sub-bank via eccentric departure solver", flush=True)


if __name__ == "__main__":
    main()
