"""E-690: COMPETENT per-pair trajectory NLP (multiple/direct shooting + hard LLO constraint).

The audit (E-687/688/689) converged: the bank is a robust local opt of our WEAK solvers (DC/Lambert/
SADE), but 2-body Lambert proves ~3700-4100 m/s transfers EXIST that those solvers can't realize
(they miss the LLO). This is the standard fix: a direct-shooting NLP where the LLO is a HARD equality
constraint (so the arrival is always feasible) and SLSQP descends total dV from a Lambert seed.

Formulation (2-leg, matches the 3-impulse decision vector):
  vars x = [raan_e, argp_e, ea_e, t0, dv0(3), dv1(3), T1, T2, raan_m, argp_m, ea_m]  (15)
  depart Earth orbit at (raan_e,argp_e,ea_e), epoch t0, burn dv0; coast T1; midcourse dv1; coast T2.
  target the synodic LLO state S = moon_orbit_state(aM,eM,iM, raan_m,argp_m,ea_m).
  constraint (eq):  arrival_position - S_position = 0   (3)  -> arrival always ON the orbit
  dv2 = S_velocity - arrival_velocity  (determined; the insertion burn)
  minimize |dv0| + |dv1| + |dv2|.
Score the resulting official row under udp.fitness to confirm validity + mass.

test:  python ch1_nlp_pair.py test [n=6]
fleet: python ch1_nlp_pair.py fleet            (re-solve all bank pairs, guard-bank if total improves)
"""
import sys, json, math, time
from copy import deepcopy
import numpy as np
import heyoka as hy
import pykep as pk
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import (LtlTrajectory, earth_orbit_state, moon_orbit_state,
                                        bcp_dyn, V, T, L, CR3BP_MU_EARTH_MOON,
                                        BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S)
from esa_spoc_26.ch1_traj_lambert_dc import best_lambert_seed
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BIG = 1e4

# --- FAST propagator: cache the heyoka integrator (the official propagate REBUILDS it every call,
#     ~100ms setup; caching gives 10-100x for the SLSQP inner loop). Same tol=1e-16 -> same physics. ---
_TA = None; _EI = []; _MI = []


def _fast_propagate(posvel, t0, DVs, Ts):
    global _TA
    if _TA is None:
        x, y, z = hy.make_vars("x", "y", "z")
        evE = hy.nt_event((x + hy.par[0]) ** 2 + y ** 2 + z ** 2 - (pk.EARTH_RADIUS + 99000) ** 2 / L ** 2,
                          callback=lambda ta, tm, d: _EI.append(tm))
        evM = hy.nt_event((x - 1 + hy.par[0]) ** 2 + y ** 2 + z ** 2 - (1737400.0 + 30000) ** 2 / L ** 2,
                          callback=lambda ta, tm, d: _MI.append(tm))
        _TA = hy.taylor_adaptive(bcp_dyn(), tol=1e-16, nt_events=[evE, evM])
        _TA.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
    _EI.clear(); _MI.clear()
    _TA.time = t0
    pv = deepcopy(posvel)
    pv[1][0] += DVs[0][0]; pv[1][1] += DVs[0][1]; pv[1][2] += DVs[0][2]
    _TA.state[:6] = list(pv[0]) + list(pv[1])
    for i, tt in enumerate(Ts):
        _TA.propagate_for(tt)
        _TA.state[3] += DVs[i + 1][0]; _TA.state[4] += DVs[i + 1][1]; _TA.state[5] += DVs[i + 1][2]
    if _EI or _MI:
        return []
    return [list(_TA.state[:3]), list(_TA.state[3:6])]


propagate = _fast_propagate


def _arrival(aE, eE, iE, x):
    raan_e, argp_e, ea_e, t0 = x[0], x[1], x[2], x[3]
    dv0 = x[4:7]; dv1 = x[7:10]; T1, T2 = x[10], x[11]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_e)
    pv1 = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]], [T1, T2])
    return pv0, pv1


def solve_pair(udp, idE, idL, restarts=4, verbose=False):
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    seed = best_lambert_seed(udp, idE, idL)
    if seed is None:
        return None
    tof_nd = seed["tof_d"] * 86400 / T
    dv0_seed = np.asarray(seed["dv1"]) / V

    def unpack(x):
        return x[:12], x[12], x[13], x[14]

    def target_state(x):
        return moon_orbit_state(aM, eM, iM, x[12], x[13], x[14])

    def objective(x):
        xa, rm, am, em = unpack(x)
        if x[10] < 0.02 or x[11] < 0.0:
            return BIG
        pv0, pv1 = _arrival(aE, eE, iE, x)
        if len(pv1) == 0:
            return BIG
        S = target_state(x)
        dv2 = np.array(S[1]) - np.array(pv1[1])      # insertion = orbit vel - arrival vel
        return (np.linalg.norm(x[4:7]) + np.linalg.norm(x[7:10]) + np.linalg.norm(dv2)) * V

    def pos_residual(x):
        pv0, pv1 = _arrival(aE, eE, iE, x)
        if len(pv1) == 0:
            return np.array([BIG, BIG, BIG])
        S = target_state(x)
        return (np.array(pv1[0]) - np.array(S[0]))     # synodic, ~O(1) units

    best = None
    for rs in range(restarts):
        # seed: Lambert departure angles + zero midcourse + split tof; arrival phase swept
        x0 = np.array([seed["raan_e"], seed["argp_e"], seed["ea_e"], 0.0,
                       *dv0_seed, 0.0, 0.0, 0.0, tof_nd * 0.5, tof_nd * 0.5,
                       seed["raan_m"] + rs * math.pi / 2, 0.0, seed["ea_m"] + rs * math.pi / 2])
        try:
            res = minimize(objective, x0, method="SLSQP",
                           constraints=[{"type": "eq", "fun": pos_residual}],
                           options={"maxiter": 200, "ftol": 1e-4})
        except Exception:
            continue
        # verify feasibility (constraint actually satisfied) + official validity
        if np.linalg.norm(pos_residual(res.x)) * L > 2000.0:   # >2 km off the orbit -> not feasible
            continue
        xa, rm, am, em = unpack(res.x)
        pv0, pv1 = _arrival(aE, eE, iE, res.x)
        if len(pv1) == 0:
            continue
        S = target_state(res.x)
        dv2 = np.array(S[1]) - np.array(pv1[1])
        row = [idE, idL, 0, float(res.x[3]), *pv0[0], *pv0[1],
               *res.x[4:7].tolist(), *res.x[7:10].tolist(), *dv2.tolist(),
               float(res.x[10]), float(res.x[11])]
        f = udp.fitness(row)
        if f[0] >= 0:                                  # official rejects -> infeasible
            continue
        tot = -311.0 * 9.80665 * math.log((-f[0] + 500.0) / 5000.0)
        if best is None or tot < best[0]:
            best = (tot, row, -f[0])
    return best


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    print("[E-690] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    bankrows = {}
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        tot = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        bankrows[(int(r[0]), int(r[1]))] = tot

    if mode == "test":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        # mix: 3 expensive circular + 3 expensive non-circular
        eL = udp.moon_data[:, 1]
        items = sorted(bankrows.items(), key=lambda kv: -kv[1])
        circ = [k for k, v in items if eL[k[1]] < 0.1][:3]
        noncirc = [k for k, v in items if eL[k[1]] >= 0.1][:3]
        picks = circ + noncirc
        print(f"[E-690] NLP test on {len(picks)} expensive pairs (3 circular + 3 eccentric)", flush=True)
        print(f"  {'pair':>12} {'bank':>7}  {'nlp':>7} {'Δ':>7} {'beats?':>7} [{'t':>4}]", flush=True)
        t0 = time.time(); wins = 0
        for (e, l) in picks:
            r = solve_pair(udp, e, l)
            b = bankrows[(e, l)]
            if r is None:
                print(f"  ({e:>4},{l:>4}) {b:7.0f}  {'FAIL':>7} [{time.time()-t0:.0f}s]", flush=True); continue
            d = b - r[0]; hit = d > 50; wins += hit
            print(f"  ({e:>4},{l:>4}) {b:7.0f}  {r[0]:7.0f} {d:+7.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
        print(f"\n[E-690] VERDICT: {wins}/{len(picks)} beaten by the NLP", flush=True)
        print("  many YES -> competent NLP realizes the cheap floor -> +100k LEVER, run fleet mode", flush=True)
    elif mode == "fleet":
        import os
        out = {}
        cache = f"{ROOT}/cache/ch1_nlp_fleet.json"
        if os.path.exists(cache):
            out = json.load(open(cache))
        keys = [k for k in bankrows if f"{k[0]}_{k[1]}" not in out]
        print(f"[E-690] FLEET: {len(out)} done, {len(keys)} to solve", flush=True)
        t0 = time.time(); imp = 0
        for n, (e, l) in enumerate(keys):
            r = solve_pair(udp, e, l, restarts=3)
            b = bankrows[(e, l)]
            if r is not None and r[0] < b - 20:
                out[f"{e}_{l}"] = {"row": r[1], "nlp_dv": r[0], "bank_dv": b}; imp += 1
            else:
                out[f"{e}_{l}"] = {"row": None, "bank_dv": b}
            if n % 10 == 0:
                json.dump(out, open(cache, "w"))
                print(f"  {n}/{len(keys)} | improved {imp} | [{(time.time()-t0)/60:.0f}min]", flush=True)
        json.dump(out, open(cache, "w"))
        gained = sum(1 for v in out.values() if v.get("row"))
        print(f"[E-690] FLEET DONE: {gained} pairs improved -> cache/ch1_nlp_fleet.json (assemble + guard-bank next)", flush=True)


if __name__ == "__main__":
    main()
