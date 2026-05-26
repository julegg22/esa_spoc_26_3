"""6-D DC with multi-restart: explore 3-impulse architecture basins.

For each (idE, idL): solve a 6-var (dv0+dv1) DC with 3-equation residual
(arrival position match). UNDER-DETERMINED system — pick solution
minimizing |dv0|+|dv1|+|dv2| (where dv2 = solve_arrival).

Multi-start with many random dv1 seeds (key: dv1 magnitude in
[100, 2000] m/s sampled from plane-change distribution).

Test on bottom-mass transfers to see if 3-impulse architectures unlock
significant gains.
"""
import numpy as np
import pykep as pk
from scipy.optimize import minimize

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric
from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0

MU = CR3BP_MU_EARTH_MOON


def try_6d_with_seed(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL,
                       T1, T2, t0, dv0_seed, dv1_seed):
    """Run scipy SLSQP minimizing total dv with arrival-position constraint."""

    def total_dv(p):
        dv0 = p[:3]
        dv1 = p[3:6]
        # dv2 computed lazily
        pv_arr = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                            [T1, T2])
        if len(pv_arr) == 0:
            return 1e6
        dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
        if dv2_res is None:
            return 1e6
        dv2, _ = dv2_res
        return (np.linalg.norm(dv0) + np.linalg.norm(dv1)
                + np.linalg.norm(dv2)) * V

    def constraint_pos(p):
        dv0 = p[:3]
        dv1 = p[3:6]
        pv_arr = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                            [T1, T2])
        if len(pv_arr) == 0:
            return np.array([1.0, 1.0, 1.0])
        # Residual in nondim units; tolerance is 384m/L = ~1e-6
        return np.array([
            pv_arr[0][0] - pv_tgt[0][0],
            pv_arr[0][1] - pv_tgt[0][1],
            pv_arr[0][2] - pv_tgt[0][2],
        ])

    x0 = np.array([*dv0_seed, *dv1_seed])
    try:
        sol = minimize(
            total_dv, x0,
            method="SLSQP",
            constraints={"type": "eq", "fun": constraint_pos},
            options={"ftol": 1e-7, "maxiter": 100, "disp": False},
        )
    except Exception:
        return None

    # Verify constraint satisfaction
    final_residual = np.linalg.norm(constraint_pos(sol.x))
    if final_residual > 1e-3:  # not close enough to feasibility
        return None

    dv0 = sol.x[:3]
    dv1 = sol.x[3:6]
    pv_arr = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    return dv0, dv1, dv2


def try_pair_multi_restart(udp, idE, idL, n_restarts=15):
    """Multi-restart 6-D DC for one pair."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    rng = np.random.default_rng(idE * 1000 + idL)
    best = None

    # Configurations to test
    for tof_d in (8, 11, 15, 20):
        for t0_val in (0.0, np.pi, 2 * np.pi):
            for split in (0.6, 0.75, 0.9):
                tof = tof_d * 86400.0 / T
                T1 = split * tof
                T2 = (1 - split) * tof
                for ea_dep in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                    pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
                    for ea_arr in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                        pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)

                        # Lambert seed for dv0
                        dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
                        if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
                            continue
                        if np.linalg.norm(dv0_seed) > 10:
                            continue

                        # Multi-start dv1 seeds: zero + several random
                        for restart in range(n_restarts):
                            if restart == 0:
                                dv1_seed = np.zeros(3)
                            else:
                                # Random direction, magnitude 100-1500 m/s
                                d = rng.standard_normal(3)
                                d /= np.linalg.norm(d)
                                mag = rng.uniform(0.1, 1.5)  # nondim ~ 100-1500 m/s
                                dv1_seed = d * mag

                            res = try_6d_with_seed(
                                udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL,
                                T1, T2, t0_val, dv0_seed, dv1_seed)
                            if res is None:
                                continue
                            dv0, dv1, dv2 = res
                            row = [idE, idL, 0, t0_val,
                                    *pv0[0], *pv0[1],
                                    *dv0.tolist(), *dv1.tolist(), *dv2.tolist(),
                                    T1, T2]
                            chr_padded = list(row)
                            pad = (udp.dim - len(chr_padded)) // 21
                            for _ in range(pad):
                                chr_padded.extend([-1.0] + [0.0] * 20)
                            f = udp.fitness(chr_padded)[0]
                            if f >= 0:
                                continue
                            mass = -f
                            if best is None or mass > best[0]:
                                best = (mass, row)
    return best


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    test_cases = [
        (0, 0, "coplanar control"),
        (213, 19, "LEO+iL=1.07"),
        (303, 109, "LEO+iL=1.08"),
        (244, 105, "LEO+iL=0.50"),
        (227, 315, "LEO+iL=0.47"),
    ]

    print("Multi-restart 6-D DC test:", flush=True)
    print(f"{'pair':>10} {'desc':<22} {'mass':>5}", flush=True)
    for idE, idL, desc in test_cases:
        t0 = time.time()
        best = try_pair_multi_restart(udp, idE, idL, n_restarts=10)
        dt = time.time() - t0
        if best:
            mass, _ = best
            print(f"  ({idE:>3},{idL:>3}) {desc:<22} {mass:>5.0f} ({dt:.0f}s)",
                  flush=True)
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<22} FAIL ({dt:.0f}s)",
                  flush=True)
