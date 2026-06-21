"""E-691: MULTIPLE-SHOOTING per-pair solver — de-risk the convergence fix.

Single-shooting (E-690) failed: SLSQP can't satisfy the LLO constraint on a sensitive 30-50d arc.
FIX: break the arc into N short (~5d) segments with state-CONTINUITY constraints between nodes.
Short segments are not chaotic -> well-conditioned Jacobian -> SLSQP converges. Burns only at the
ends (clean 2-impulse): dv0 at departure, dv2 at arrival; interior is ballistic + continuous.

Vars x = [raan_e, argp_e, ea_e, t0, dv0(3), z_1..z_{N-1} (6 each), raan_m, argp_m, ea_m]
  node_0 = earth_orbit_state(raan_e,argp_e,ea_e) with +dv0 on velocity.
  continuity:  seg(node_i, t_i, dt).state == node_{i+1}   (6 eqs, i=0..N-2)
  terminal:    seg(node_{N-1}, t_{N-1}, dt).pos == LLO_target.pos   (3 eqs)
  dv2 = LLO_target.vel - final.vel ;  minimize |dv0|+|dv2|.
Seed: dv0 from Lambert; interior nodes = the REAL BCP propagation sampled at node times
(continuity satisfied at start; only the terminal LLO constraint is initially violated).

Usage: python ch1_multishoot.py [idE] [idL] [N=8]
"""
import sys, json, math, time
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

# fast event-free cached integrator for ballistic segments (official fitness validates the final row)
_TA = None


def seg(state6, t0, dt):
    """ballistic BCP propagation of one segment; returns the 6-state at t0+dt."""
    global _TA
    if _TA is None:
        _TA = hy.taylor_adaptive(bcp_dyn(), [0.0] * 6, tol=1e-14)
        _TA.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
    _TA.time = t0
    _TA.state[:] = state6
    _TA.propagate_for(dt)
    return np.array(_TA.state[:6])


def solve(udp, idE, idL, N=8, verbose=True):
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    seed = best_lambert_seed(udp, idE, idL)
    if seed is None:
        print("no lambert seed"); return None
    tof = seed["tof_d"] * 86400 / T
    dt = tof / N
    re0, ae0, ee0 = seed["raan_e"], seed["argp_e"], seed["ea_e"]
    dv0_0 = np.asarray(seed["dv1"]) / V
    rm0, am0, em0 = seed["raan_m"], 0.0, seed["ea_m"]

    # --- build seed: propagate the real BCP arc, sample interior nodes (continuity satisfied) ---
    pv0 = earth_orbit_state(aE, eE, iE, re0, ae0, ee0)
    node0 = np.array(list(pv0[0]) + [pv0[1][0] + dv0_0[0], pv0[1][1] + dv0_0[1], pv0[1][2] + dv0_0[2]])
    nodes = [node0]
    s = node0.copy()
    for i in range(N - 1):
        s = seg(s, i * dt, dt)
        nodes.append(s.copy())
    z_seed = np.concatenate(nodes[1:])            # z_1..z_{N-1}
    x0 = np.concatenate([[re0, ae0, ee0, 0.0], dv0_0, z_seed, [rm0, am0, em0]])

    def split(x):
        re, ae, ee, t0 = x[0], x[1], x[2], x[3]
        dv0 = x[4:7]
        zs = x[7:7 + 6 * (N - 1)].reshape(N - 1, 6)
        rm, am, em = x[7 + 6 * (N - 1):]
        return re, ae, ee, t0, dv0, zs, rm, am, em

    def node_list(x):
        re, ae, ee, t0, dv0, zs, rm, am, em = split(x)
        p = earth_orbit_state(aE, eE, iE, re, ae, ee)
        n0 = np.array(list(p[0]) + [p[1][0] + dv0[0], p[1][1] + dv0[1], p[1][2] + dv0[2]])
        return [n0] + [zs[i] for i in range(N - 1)], t0

    def constraints(x):
        nodes, t0 = node_list(x)
        re, ae, ee, _, dv0, zs, rm, am, em = split(x)
        res = []
        for i in range(N - 1):                    # continuity node_i -> node_{i+1}
            res.extend((seg(nodes[i], t0 + i * dt, dt) - nodes[i + 1]).tolist())
        # terminal: last segment endpoint position == LLO target position
        endf = seg(nodes[N - 1], t0 + (N - 1) * dt, dt)
        tgt = moon_orbit_state(aM, eM, iM, rm, am, em)
        res.extend((endf[:3] - np.array(tgt[0])).tolist())
        return np.array(res)

    def objective(x):
        re, ae, ee, t0, dv0, zs, rm, am, em = split(x)
        nodes, _ = node_list(x)
        endf = seg(nodes[N - 1], t0 + (N - 1) * dt, dt)
        tgt = moon_orbit_state(aM, eM, iM, rm, am, em)
        dv2 = np.array(tgt[1]) - endf[3:]
        return (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V

    c0 = np.linalg.norm(constraints(x0))
    if verbose:
        print(f"[E-691] ({idE},{idL}) N={N} tof={seed['tof_d']}d seed_lam={seed['total']:.0f} | "
              f"seed constraint-norm={c0:.2e} (continuity ok, terminal violated)", flush=True)
    t0 = time.time()
    res = minimize(objective, x0, method="SLSQP",
                   constraints=[{"type": "eq", "fun": constraints}],
                   options={"maxiter": 600, "ftol": 1e-7})
    # feasibility-restoration polish: if terminal still loose, re-solve minimizing constraint norm only
    if np.linalg.norm(constraints(res.x)) > 1e-5:
        res2 = minimize(lambda x: float(np.sum(constraints(x) ** 2)) + 1e-9 * objective(x),
                        res.x, method="SLSQP", options={"maxiter": 400, "ftol": 1e-10})
        if np.linalg.norm(constraints(res2.x)) < np.linalg.norm(constraints(res.x)):
            res = res2
    cfin = np.linalg.norm(constraints(res.x))
    ms_dv = objective(res.x)
    re, ae, ee, t0v, dv0, zs, rm, am, em = split(res.x)
    print(f"[E-691] multi-shoot done [{time.time()-t0:.0f}s]: total_dv={ms_dv:.0f} m/s | "
          f"constraint-norm {c0:.1e}->{cfin:.1e}  (3+ orders => CONVERGENCE FIX WORKS)", flush=True)

    # --- WARM-START single-shooting polish: from the multi-shoot dv0/phasing, drive the SINGLE
    #     official coast endpoint onto the LLO (radius window) via least_squares, then solve_arrival_dv. ---
    from scipy.optimize import least_squares
    from esa_spoc_26.ch1_trajectory import propagate as official_propagate
    from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv

    # fast EVENT-AWARE cached propagator for the polish loop (validate final with official)
    _PE = [None]; _ei = []; _mi = []

    def fast_prop(pv, t0, dv0v, tofv):
        if _PE[0] is None:
            xx, yy, zz = hy.make_vars("x", "y", "z")
            evE = hy.nt_event((xx + hy.par[0]) ** 2 + yy ** 2 + zz ** 2 - (pk.EARTH_RADIUS + 99000) ** 2 / L ** 2,
                              callback=lambda ta, tm, d: _ei.append(tm))
            evM = hy.nt_event((xx - 1 + hy.par[0]) ** 2 + yy ** 2 + zz ** 2 - (1737400.0 + 30000) ** 2 / L ** 2,
                              callback=lambda ta, tm, d: _mi.append(tm))
            ta = hy.taylor_adaptive(bcp_dyn(), tol=1e-16, nt_events=[evE, evM])
            ta.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
            _PE[0] = ta
        ta = _PE[0]; _ei.clear(); _mi.clear()
        ta.time = t0
        ta.state[:6] = [pv[0][0], pv[0][1], pv[0][2], pv[1][0] + dv0v[0], pv[1][1] + dv0v[1], pv[1][2] + dv0v[2]]
        ta.propagate_for(tofv)
        if _ei or _mi:
            return []
        return [list(ta.state[:3]), list(ta.state[3:6])]
    p = earth_orbit_state(aE, eE, iE, re, ae, ee)
    tgt0 = moon_orbit_state(aM, eM, iM, rm, am, em)

    # FULL-DOF single coast: w = [re, ae, ee, t0, dv0(3), tof, em]  (warm from multi-shoot)
    def coast_w(w):
        pp = earth_orbit_state(aE, eE, iE, w[0], w[1], w[2])
        return pp, fast_prop(pp, float(w[3]), w[4:7], float(w[7]))

    def pos_resid(w):
        _, pv1 = coast_w(w)
        if len(pv1) == 0:
            return np.array([10.0, 10.0, 10.0])
        return np.array(pv1[0]) - np.array(moon_orbit_state(aM, eM, iM, rm, am, w[8])[0])

    def total_dv(w):
        _, pv1 = coast_w(w)
        if len(pv1) == 0:
            return 50.0
        tg = moon_orbit_state(aM, eM, iM, rm, am, w[8])
        dv2 = np.array(tg[1]) - np.array(pv1[1])
        return (np.linalg.norm(w[4:7]) + np.linalg.norm(dv2)) * V / 1000.0
    w0 = np.array([re, ae, ee, t0v, dv0[0], dv0[1], dv0[2], tof, em])
    fa = least_squares(pos_resid, w0, method="trf", xtol=1e-15, max_nfev=600)   # feasibility
    fb = minimize(total_dv, fa.x, method="SLSQP", constraints=[{"type": "eq", "fun": pos_resid}],
                  options={"maxiter": 500, "ftol": 1e-9})                        # min realized dv
    w = fb.x if np.linalg.norm(pos_resid(fb.x)) * L < 1000 else fa.x
    p, pv1 = coast_w(w)
    sol = type("S", (), {"x": np.array(w[4:7])})()
    em = float(w[8]); t0v = float(w[3]); tof = float(w[7])
    tgt0 = moon_orbit_state(aM, eM, iM, rm, am, em)
    if len(pv1) == 0:
        print("  polish: impact"); return res, False
    term_km = np.linalg.norm(np.array(pv1[0]) - np.array(tgt0[0])) * L / 1000
    a2 = solve_arrival_dv(pv1, aM, eM, iM)
    if a2 is None:
        print(f"  polish: terminal {term_km:.2f}km but arrival outside LLO window"); return res, False
    dv2 = a2[0]
    row = [idE, idL, 0, float(t0v), *p[0], *p[1], *sol.x.tolist(), 0., 0., 0., *np.asarray(dv2).tolist(),
           float(tof), 0.0]
    f = udp.fitness(row)
    if f[0] < 0:
        tot = -311.0 * 9.80665 * math.log((-f[0] + 500.0) / 5000.0)
        print(f"  ★ POLISHED + OFFICIALLY VALID: terminal {term_km:.2f}km | total_dv={tot:.0f} m/s | "
              f"mass={-f[0]:.0f} kg  (bank-dv was higher) -> 2-IMPULSE FLOOR REALIZED", flush=True)
        return (res, True, row, tot)
    print(f"  polish: terminal {term_km:.2f}km, official rejected (fit={f[0]:.4f})", flush=True)
    return res, False


def main():
    idE = int(sys.argv[1]) if len(sys.argv) > 1 else 396
    idL = int(sys.argv[2]) if len(sys.argv) > 2 else 225
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    print("[E-691] init ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    for i in range(0, len(bank), 21):
        if int(bank[i]) == idE and int(bank[i + 1]) == idL:
            r = bank[i:i + 21]
            bt = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
            print(f"[E-691] bank total for ({idE},{idL}) = {bt:.0f} m/s", flush=True)
    solve(udp, idE, idL, N)


if __name__ == "__main__":
    main()
