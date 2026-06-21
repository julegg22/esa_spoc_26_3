"""E-698: robust per-pair MINIMUM-ENERGY trajectory solver (the breakthrough realized).
Perilune-targeting + smooth-penalty GLOBAL CMA-ES (escapes the bank's basin) + local refinement +
OFFICIAL validation. The reusable engine for the fleet sweep.

solve_pair(udp, idE, idL, ...) -> (best_dv_ms, official_row, mass) or None.
CLI test: python ch1_minenergy_solver.py test [n=6]
"""
import sys, json, math, time
import numpy as np
import heyoka as hy
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import (LtlTrajectory, earth_orbit_state, state2moon, bcp_dyn, V, L, T,
                                        CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
from scipy.optimize import least_squares
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi
mu = CR3BP_MU_EARTH_MOON
_TAF = None   # fast (1e-12) for the search
_TAA = None   # accurate (1e-16) for official-row construction


def prop_to_peri(pv0, t0, dv0, tof_max, fast=True):
    """forward to the natural perilune; return (state, peri_radius_nondim, T1_duration_nondim) or (None,..)."""
    global _TAF, _TAA
    if fast:
        if _TAF is None:
            _TAF = hy.taylor_adaptive(bcp_dyn(), [0.0] * 6, tol=1e-12)
            _TAF.pars[:] = [mu, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
        _TA = _TAF; step = 0.30
    else:
        if _TAA is None:
            _TAA = hy.taylor_adaptive(bcp_dyn(), [0.0] * 6, tol=1e-16)
            _TAA.pars[:] = [mu, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
        _TA = _TAA; step = 0.10
    _TA.time = t0
    _TA.state[:6] = [pv0[0][0], pv0[0][1], pv0[0][2],
                     pv0[1][0] + dv0[0], pv0[1][1] + dv0[1], pv0[1][2] + dv0[2]]
    peri = 1e9; pst = None; pt = 0.0; prev = 1e9; rising = 0
    R_imp = (1737400.0 + 4000) / L
    n = max(20, int(tof_max / step)); dt = tof_max / n
    for k in range(n):
        _TA.propagate_for(dt)
        s = _TA.state
        rm = math.sqrt((s[0] - 1 + mu) ** 2 + s[1] ** 2 + s[2] ** 2)
        if rm < peri:
            peri = rm; pst = [list(s[:3]), list(s[3:6])]; pt = (k + 1) * dt
        if rm < R_imp:
            return None, peri, pt
        if rm > prev:
            rising += 1
            if rising > 3 and peri < 0.04:
                break
        else:
            rising = 0
        prev = rm
    return pst, peri, pt


class UDP:
    def __init__(self, udp, idE, idL, tof_max):
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aM, self.eM, self.iM = udp.moon_data[idL]
        self.tof_max = tof_max

    def get_bounds(self):
        return ([0, 0, 0, 0, -5, -5, -5], [TWO_PI, TWO_PI, TWO_PI, TWO_PI, 5, 5, 5])

    def _eval(self, x):
        pv0 = earth_orbit_state(self.aE, self.eE, self.iE, x[0], x[1], x[2])
        st, peri, pt = prop_to_peri(pv0, x[3], x[4:7], self.tof_max)
        return pv0, st, peri, pt

    def fitness(self, x):
        try:
            pv0, st, peri, pt = self._eval(x)
        except Exception:
            return [3e4]
        miss = abs(peri * L - self.aM) / 1000.0
        if st is not None:
            a2 = solve_arrival_dv(st, self.aM, self.eM, self.iM)
            if a2 is not None:
                return [(np.linalg.norm(x[4:7]) + np.linalg.norm(a2[0])) * V]
            # not insertable: penalize radius miss AND approach-plane (inclination) mismatch,
            # so the search lands plane-compatible (solve_arrival_dv needs latitude<=i_m)
            try:
                inc_miss = abs(state2moon([st[0], st[1]])[2] - self.iM) * 3000.0
            except Exception:
                inc_miss = 3000.0
            return [1.25e4 + min(miss, 6000.0) + min(inc_miss, 4000.0)]
        return [1.25e4 + min(miss, 6000.0) + 2000.0]


def official_row(udp, idE, idL, x, tof_max=16.0):
    """build + score the official 2-impulse perilune row (ACCURATE perilune); return (row, dv_ms, mass) or None."""
    aE, eE, iE = udp.earth_data[idE]; aM, eM, iM = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, x[0], x[1], x[2])
    st, peri, pt = prop_to_peri(pv0, x[3], x[4:7], tof_max, fast=False)   # 1e-16 for the row
    if st is None:
        return None
    a2 = solve_arrival_dv(st, aM, eM, iM)
    if a2 is None:
        return None
    dv2 = a2[0]
    row = [idE, idL, 0, float(x[3]), *pv0[0], *pv0[1], *np.asarray(x[4:7]).tolist(),
           0.0, 0.0, 0.0, *np.asarray(dv2).tolist(), float(pt), 0.0]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    dv = (np.linalg.norm(x[4:7]) + np.linalg.norm(dv2)) * V
    return row, dv, -f


def _off_obj(udp, idE, idL, tof_max, x):
    """official-precision (1e-16) objective: valid -> total dv; invalid -> smooth 1e-16 perilune-miss penalty."""
    aE, eE, iE = udp.earth_data[idE]; aM, eM, iM = udp.moon_data[idL]
    try:
        pv0 = earth_orbit_state(aE, eE, iE, x[0], x[1], x[2])
        st, peri, pt = prop_to_peri(pv0, x[3], x[4:7], tof_max, fast=False)
    except Exception:
        return 3e4
    miss = abs(peri * L - aM) / 1000.0
    if st is not None:
        a2 = solve_arrival_dv(st, aM, eM, iM)
        if a2 is not None:
            row = [idE, idL, 0, float(x[3]), *pv0[0], *pv0[1], *np.asarray(x[4:7]).tolist(),
                   0.0, 0.0, 0.0, *np.asarray(a2[0]).tolist(), float(pt), 0.0]
            if udp.fitness(row)[0] < 0:                  # OFFICIALLY valid
                return (np.linalg.norm(x[4:7]) + np.linalg.norm(a2[0])) * V
    return 1.3e4 + miss


def precise_dc(udp, idE, idL, x, tof_max):
    """precise differential correction: adjust the 7-DOF x so the OFFICIAL post-insertion orbit
    matches (aM,eM,iM) to the validator's tolerance. Returns the corrected x."""
    aE, eE, iE = udp.earth_data[idE]; aM, eM, iM = udp.moon_data[idL]

    def resid(z):
        try:
            pv0 = earth_orbit_state(aE, eE, iE, z[0], z[1], z[2])
            st, peri, pt = prop_to_peri(pv0, z[3], z[4:7], tof_max, fast=False)
        except Exception:
            return [1.0, 1.0, 1.0]
        if st is None:
            return [1.0, 1.0, 1.0]
        a2 = solve_arrival_dv(st, aM, eM, iM)
        if a2 is None:
            # not insertable yet: steer BOTH the perilune radius AND the approach-orbit inclination
            # (solve_arrival_dv needs the arrival plane compatible with iM, not just the radius)
            el_arr = state2moon([st[0], st[1]])
            return [(peri * L - aM) / L, (el_arr[2] - iM) * 2.0, 0.0]
        final = [st[0], [st[1][i] + a2[0][i] for i in range(3)]]
        el = state2moon(final)                              # (a,e,i,...)
        return [(el[0] - aM) / L, el[1] - eM, el[2] - iM]    # official match residual

    x0 = np.asarray(x)
    sol = least_squares(resid, x0, method="trf", xtol=1e-14, max_nfev=200,
                        bounds=(x0 - [1.0, 1.0, 1.0, 2.0, 1.5, 1.5, 1.5],
                                x0 + [1.0, 1.0, 1.0, 2.0, 1.5, 1.5, 1.5]))
    return sol.x


def solve_pair(udp, idE, idL, restarts=8, gen=200, tof_max=16.0, seed0=0, verbose=False):
    prob = pg.problem(UDP(udp, idE, idL, tof_max))
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-6, xtol=1e-6))
    best = None
    for rs in range(restarts):
        rng = np.random.default_rng(seed0 + 1009 * rs + idE * 7 + idL)
        pop = pg.population(prob, size=0)
        for _ in range(22):
            pop.push_back(lb + rng.random(7) * (ub - lb))
        pop = cma.evolve(pop)
        xb = pop.champion_x; fb = float(pop.champion_f[0])
        if fb < 1.2e4:                                  # feasible at 1e-12 -> refine to OFFICIAL 1e-16
            res = minimize(lambda z: prob.fitness(z)[0], xb, method="Nelder-Mead",
                           options={"maxiter": 400, "fatol": 1e-3, "xatol": 1e-7})
            if prob.fitness(res.x)[0] < fb:
                xb = res.x
            # PRECISE DC: drive the official (a,e,i) match to tolerance, then validate
            xf = precise_dc(udp, idE, idL, xb, tof_max)
            ov = official_row(udp, idE, idL, xf, tof_max)
            if ov is None:                                   # DC from the raw search point as fallback
                xf2 = precise_dc(udp, idE, idL, xb + 0 * xb, tof_max)
                ov = official_row(udp, idE, idL, xf2, tof_max)
            if ov is not None and (best is None or ov[1] < best[1]):
                best = ov
                if verbose:
                    print(f"      rs{rs}: feas {fb:.0f} -> DC -> OFFICIAL VALID dv={ov[1]:.0f} mass={ov[2]:.0f}", flush=True)
            elif verbose:
                print(f"      rs{rs}: feas {fb:.0f}, DC did not reach the 384m window (official rejected)", flush=True)
    return best


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    print("[E-698] init ...", flush=True)
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
    print(f"[E-698] {mode}: per-pair min-energy solver on {n} most-expensive pairs", flush=True)
    print(f"  {'pair':>12} {'eL':>5} {'bank':>7}  {'nrg':>7} {'Δdv':>7} {'+kg':>6} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0; tot_kg = 0.0
    for dv, e, l, el in rows[:n]:
        print(f"  --- ({e},{l}) bank={dv:.0f} ---", flush=True)
        res = solve_pair(udp, e, l, restarts=6, gen=160, verbose=True)
        if res is None:
            print(f"  ({e:>4},{l:>4}) {el:5.2f} {dv:7.0f}  {'FAIL':>7} [{time.time()-t0:.0f}s]", flush=True); continue
        row, ndv, mass = res
        bmass = math.exp(-dv / 3050.0) * 5000 - 500
        d = dv - ndv; kg = mass - bmass; hit = d > 30; wins += hit; tot_kg += max(kg, 0)
        print(f"  ({e:>4},{l:>4}) {el:5.2f} {dv:7.0f}  {ndv:7.0f} {d:+7.0f} {kg:+6.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-698] VERDICT: {wins}/{n} beaten; +{tot_kg:.0f} kg on these pairs", flush=True)


if __name__ == "__main__":
    main()
