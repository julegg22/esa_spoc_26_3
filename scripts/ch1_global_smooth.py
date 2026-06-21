"""E-697: GLOBAL basin search with a SMOOTH feasibility penalty (user insight: we kept polishing the
bank's basin because the HARD constant penalty gave the optimizer no gradient off the feasible
manifold). FIX: infeasible trajectories return BASE + smooth distance-to-LLO, so CMA-ES/SA can
navigate ONTO the thin manifold from anywhere and explore ALTERNATIVE basins (incl the slow-arrival
min-energy basin, dv2~875 vs bank's fast-arrival 2434). NOT bank-anchored: diverse random init.

Runs CMA-ES (multi-restart) AND SA on the expensive circular pairs. Beats bank -> alternative basin found.
"""
import sys, json, math, time
from copy import deepcopy
import numpy as np
import heyoka as hy
import pykep as pk
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import (LtlTrajectory, earth_orbit_state, bcp_dyn, V, L, T,
                                        CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi
mu = CR3BP_MU_EARTH_MOON

# fast cached event-aware propagator (the official one REBUILDS the integrator every call)
_TA = None; _EI = []; _MI = []


def propagate_to_peri(posvel, t0, dv0, tof_max):
    """propagate forward until the natural PERILUNE (closest Moon approach); arrival = that state.
    Returns (state_at_perilune_or_None_if_impact, perilune_radius_nondim)."""
    global _TA
    if _TA is None:
        _TA = hy.taylor_adaptive(bcp_dyn(), [0.0] * 6, tol=1e-14)
        _TA.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
    _TA.time = t0
    _TA.state[:6] = [posvel[0][0], posvel[0][1], posvel[0][2],
                     posvel[1][0] + dv0[0], posvel[1][1] + dv0[1], posvel[1][2] + dv0[2]]
    peri = 1e9; peri_state = None; prev = 1e9; rising = 0
    R_imp = (1737400.0 + 5000) / L
    n = max(20, int(tof_max / 0.2)); dt = tof_max / n
    for _ in range(n):
        _TA.propagate_for(dt)
        s = _TA.state
        rm = math.sqrt((s[0] - 1 + mu) ** 2 + s[1] ** 2 + s[2] ** 2)
        if rm < peri:
            peri = rm; peri_state = [list(s[:3]), list(s[3:6])]
        if rm < R_imp:
            return None, peri
        if rm > prev:
            rising += 1
            if rising > 3 and peri < 0.05:    # passed a perilune that came near the Moon
                break
        else:
            rising = 0
        prev = rm
    return peri_state, peri


class PairUDPSmooth:
    def __init__(self, udp, idE, idL):
        self.udp = udp; self.idE = idE; self.idL = idL
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aM, self.eM, self.iM = udp.moon_data[idL]

    def get_bounds(self):                        # 7 DOF: depart phasing + epoch + dv0; arrive at perilune
        lb = [0, 0, 0, 0, -5, -5, -5]
        ub = [TWO_PI, TWO_PI, TWO_PI, TWO_PI, 5, 5, 5]
        return (lb, ub)

    def fitness(self, x):
        raan_e, argp_e, ea, t0 = x[:4]; dv0 = x[4:7]
        try:
            pv0 = earth_orbit_state(self.aE, self.eE, self.iE, raan_e, argp_e, ea)
            st, peri = propagate_to_peri(pv0, t0, dv0, 15.0)   # up to ~65d to find perilune
        except Exception:
            return [2e4]
        peri_miss_km = abs(peri * L - self.aM) / 1000.0
        if st is not None:
            a2 = solve_arrival_dv(st, self.aM, self.eM, self.iM)
            if a2 is not None:                   # FEASIBLE: total = dv0 + insertion (clean 2-impulse)
                tot = (np.linalg.norm(dv0) + np.linalg.norm(a2[0])) * V
                return [min(tot, 1.2e4)]
        # infeasible: UNCAPPED smooth gradient (perilune -> LLO radius), pulling the arc in from anywhere
        return [1.25e4 + peri_miss_km]


def run(prob, algo, n_restarts, seed0, tag=""):
    """sequential in-process restarts (archipelago multiprocessing can't pickle the heyoka integrator)."""
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    best = 1e18; t0 = time.time()
    for k in range(n_restarts):
        rng = np.random.default_rng(seed0 + 1009 * k)
        pop = pg.population(prob, size=0)
        for _ in range(24):
            pop.push_back(lb + rng.random(len(lb)) * (ub - lb))   # DIVERSE random init, NOT bank-anchored
        pop = algo.evolve(pop)
        best = min(best, float(pop.champion_f[0]))
        feas = "FEASIBLE" if best < 1.2e4 else f"infeasible(peri-miss~{best-12500:.0f}km)"
        print(f"    {tag} restart {k+1}/{n_restarts}: best={best:.0f} [{feas}] [{time.time()-t0:.0f}s]", flush=True)
    return best


def main(pairs):
    print("[E-697] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    br = {}
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        br[(int(r[0]), int(r[1]))] = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
    print(f"  {'pair':>12} {'bank':>7}  {'cmaes':>7} {'sa':>7} {'best':>7} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0
    cma = pg.algorithm(pg.cmaes(gen=150, force_bounds=True, ftol=1e-5, xtol=1e-5))
    sa = pg.algorithm(pg.simulated_annealing(Ts=1000., Tf=0.01, n_T_adj=20, n_range_adj=10, bin_size=10))
    for (e, l) in pairs:
        bd = br[(e, l)]
        prob = pg.problem(PairUDPSmooth(udp, e, l))
        print(f"  --- pair ({e},{l}) bank={bd:.0f}, smooth-penalty global search (does it reach FEASIBLE off-bank?) ---", flush=True)
        c = run(prob, cma, 3, 7 * e + l, tag="cma")
        s = run(prob, sa, 2, 31 * e + l, tag="sa ")
        best = min(c, s)
        d = bd - best if best < 1.2e4 else float("nan")
        hit = best < bd - 50; wins += hit
        bs = f"{best:7.0f}" if best < 1.2e4 else "FEAS?"
        print(f"  ({e:>4},{l:>4}) {bd:7.0f}  {c:7.0f} {s:7.0f} {bs} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-697] VERDICT: {wins}/{len(pairs)} circular pairs beaten by SMOOTH-penalty global search", flush=True)
    print("  >0 -> alternative (slow-arrival) basin FOUND -> the hard penalty was the trap -> +117k LEVER ALIVE", flush=True)
    print("  0  -> even smooth global search stays >= bank -> bank basin genuinely best reachable", flush=True)


if __name__ == "__main__":
    main([(241, 50)])
