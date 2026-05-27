"""Joint NLP solver for Ch1 trajectory (audit fixes B2 + B3).

The old C-022 `try_bcp_apogee_3impulse` uses a 3-dof DC to force position
match against an over-constrained pv_tgt (B2). This module replaces it
with a true 8-dof optimization (B3) minimizing total dv directly:

Variables: [dv0_x, dv0_y, dv0_z, dv1_x, dv1_y, dv1_z, T1, T2] (8 vars)
Objective: ||dv0|| + ||dv1|| + ||dv2_implicit||  where
   dv2_implicit = solve_arrival_eccentric(propagate(pv0, t0, [dv0, dv1, 0], [T1, T2]))
No explicit equality constraints — solve_arrival_eccentric does the
(a, e, i) match implicitly; arrival RAAN/argp/ea are free (B2).

Seeded from a Hohmann dv0 and dv1=0, T1=T1_hohmann, T2=0 (= old 2-impulse
when DC was noop). Plus 4 random restarts.
"""
import numpy as np
import pykep as pk
from scipy.optimize import minimize

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def _R(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _hohmann_seed_inertial(pv0, t0, tof_d):
    """Lambert-seeded dv0 (synodic-basis at t0, nondim) for given TOF."""
    r0_synb = np.array([(pv0[0][0] + MU) * L, pv0[0][1] * L, pv0[0][2] * L])
    v0_synb = np.array([(pv0[1][0] - pv0[0][1]) * V,
                          ((pv0[1][1] + pv0[0][0]) + MU) * V,
                          pv0[1][2] * V])
    R_t0 = _R(t0)
    r0_in = R_t0 @ r0_synb
    v0_in = R_t0 @ v0_synb

    tof_nondim = tof_d * 86400.0 / T
    R_arr = _R(t0 + tof_nondim)
    r_moon_in = R_arr @ np.array([(1 - MU) * L, 0.0, 0.0])

    try:
        lp = pk.lambert_problem(r0_in.tolist(), r_moon_in.tolist(),
                                  tof_d * 86400.0, MU_EARTH, False, 0)
        v1_in = np.array(lp.get_v1()[0])
    except Exception:
        return None
    dv0_in = v1_in - v0_in
    dv0_synb = R_t0.T @ dv0_in
    return dv0_synb / V


def _evaluate(x, udp, pv0, t0, aL, eL, iL):
    """Total dv objective for one [dv0(3), dv1(3), T1, T2] candidate."""
    dv0 = x[:3]
    dv1 = x[3:6]
    T1 = max(x[6], 0.05)
    T2 = max(x[7], 0.0)
    pv_arr = propagate(pv0, t0,
                        [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return 1e6
    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return 1e6
    dv2_syn, _ = res
    dv_tot = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
              + np.linalg.norm(dv2_syn)) * V
    if dv_tot > 12000:  # 12 km/s sanity cap → almost no mass
        return 1e6
    return dv_tot


def try_nlp_solve(udp, idE, idL, raan_e, argp_e, ea_dep, t0,
                   tof_d_seed=8.0, n_restarts=3):
    """One NLP attempt for (idE, idL) at given (raan_e, argp_e, ea_dep, t0).

    Returns (mass, row, dv_ms) or None.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    best = None  # (dv_tot, x_sol)
    rng = np.random.default_rng(idE * 1000 + idL)

    for seed_idx in range(n_restarts + 1):
        # Build initial guess
        if seed_idx == 0:
            tof_d = tof_d_seed
        else:
            tof_d = rng.uniform(4.0, 18.0)
        dv0_seed = _hohmann_seed_inertial(pv0, t0, tof_d)
        if dv0_seed is None or np.linalg.norm(dv0_seed) > 8:
            continue
        T1_seed = tof_d * 86400.0 / T
        if seed_idx == 0:
            dv1_seed = np.zeros(3)
            T2_seed = 0.0
        else:
            # Random dv1 in a small nondim sphere
            d = rng.standard_normal(3)
            d /= np.linalg.norm(d) + 1e-12
            dv1_seed = d * rng.uniform(0.0, 0.3)  # nondim ~0-300 m/s
            T2_seed = rng.uniform(0.0, 1.5)

        x0 = np.array([*dv0_seed, *dv1_seed, T1_seed, T2_seed])
        try:
            sol = minimize(_evaluate, x0, args=(udp, pv0, t0, aL, eL, iL),
                            method="Nelder-Mead",
                            options={"xatol": 1e-3, "fatol": 1.0,
                                      "maxiter": 200, "maxfev": 200})
        except Exception:
            continue
        if not sol.success or sol.fun > 1e5:
            continue
        if best is None or sol.fun < best[0]:
            best = (sol.fun, sol.x)

    if best is None:
        return None

    # Reconstruct row from best x
    dv0 = best[1][:3]
    dv1 = best[1][3:6]
    T1 = max(best[1][6], 0.05)
    T2 = max(best[1][7], 0.0)
    pv_arr = propagate(pv0, t0,
                        [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return None
    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return None
    dv2, _ = res
    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0.tolist(), *dv1.tolist(), *dv2.tolist(),
            T1, T2]
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = best[0]
    return mass, row, dv_ms


def sweep_nlp(udp, idE, idL,
                raan_grid=None, argp_grid=None, ea_grid=None,
                t0_grid=None):
    """Grid sweep over (raan_e, argp_e, ea_dep, t0) for one pair."""
    if raan_grid is None:
        raan_grid = np.linspace(0, 2 * np.pi, 4, endpoint=False)
    if argp_grid is None:
        argp_grid = (0.0, np.pi)
    if ea_grid is None:
        ea_grid = (0.0, np.pi)
    if t0_grid is None:
        t0_grid = (0.0, np.pi)
    best = None
    for raan_e in raan_grid:
        for argp_e in argp_grid:
            for ea_dep in ea_grid:
                for t0_val in t0_grid:
                    res = try_nlp_solve(udp, idE, idL, raan_e, argp_e,
                                          ea_dep, t0_val)
                    if res is not None and (best is None or res[0] > best[0]):
                        best = res
    return best


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    test_cases = [
        (0, 0, "coplanar LMO (bank 819)"),
        (213, 19, "LEO low-iE + iL=1.07 (bank 5)"),
        (244, 105, "LEO + iL=0.50 (bank 374)"),
        (21, 200, "LEO + high-eL mid-iL (bank 1095)"),
        (277, 189, "GEO + high-eL (bank 2628)"),
    ]
    print(f"{'pair':>10} {'desc':<40} {'mass':>5}  {'time':>5}")
    for idE, idL, desc in test_cases:
        t_start = time.time()
        best = sweep_nlp(udp, idE, idL)
        dt = time.time() - t_start
        if best:
            print(f"  ({idE:>3},{idL:>3}) {desc:<40} {best[0]:>5.0f}  {dt:>5.1f}s")
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<40}  FAIL  {dt:>5.1f}s")
