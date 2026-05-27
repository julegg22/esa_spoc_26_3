"""2-impulse Lambert + free-arrival-point LOI (audit fix B2).

The spec says only (a, e, i) of the Moon orbit are matched — RAAN, argp,
true anomaly are *free*. The old C-022 architecture over-constrains by
fixing pv_tgt to (raan_l=argp_l=0, ea_arr ∈ small grid) and forcing
position match.

This module drops that constraint entirely:

1. For a given (idE, idL, raan_e, argp_e, ea_dep, t0) and target TOF:
   - Compute pv0 on Earth orbit
   - Use Lambert (Earth two-body) to find dv0 that takes pv0 → Moon's
     position at arrival time (= Moon-encounter trajectory)
2. Propagate the BCP dynamics for TOF with dv0 only (dv1=0, dv2=0)
3. Call solve_arrival_eccentric on the resulting state to find dv2
4. Validate via UDP fitness

Sweep over (raan_e, argp_e, ea_dep, t0, TOF) and keep best (max mass).
"""
import numpy as np
import pykep as pk

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


def try_two_impulse(udp, idE, idL, raan_e, argp_e, ea_dep, t0, tof_d):
    """One Lambert-seeded 2-impulse attempt for (idE, idL).

    Returns (mass, row, dv_ms) or None.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    # Express pv0 in *inertial* frame (fixed, = synodic basis at instant 0)
    # Step 1: pv0 in synodic-basis-at-instant-t0 (Earth-centered, no R(t)):
    r0_synbasis = np.array([(pv0[0][0] + MU) * L,
                              pv0[0][1] * L,
                              pv0[0][2] * L])
    v0_synbasis = np.array([(pv0[1][0] - pv0[0][1]) * V,
                              ((pv0[1][1] + pv0[0][0]) + MU) * V,
                              pv0[1][2] * V])
    # Step 2: rotate by t0 into inertial
    R_t0 = _R(t0)
    r0_inertial = R_t0 @ r0_synbasis
    v0_inertial = R_t0 @ v0_synbasis

    # Moon position at arrival, in inertial frame
    tof_nondim = tof_d * 86400.0 / T
    t_arr = t0 + tof_nondim
    R_arr = _R(t_arr)
    r_moon_inertial = R_arr @ np.array([(1 - MU) * L, 0.0, 0.0])

    tof_s = tof_d * 86400.0
    try:
        lp = pk.lambert_problem(r0_inertial.tolist(),
                                  r_moon_inertial.tolist(),
                                  tof_s, MU_EARTH, False, 0)
        v1_inertial = np.array(lp.get_v1()[0])
    except Exception:
        return None
    if not np.all(np.isfinite(v1_inertial)):
        return None

    dv0_inertial = v1_inertial - v0_inertial
    # Convert to synodic-basis-at-instant-t0 (= R(t0)^-1 = R(-t0))
    dv0_synbasis = R_t0.T @ dv0_inertial
    dv0_syn = dv0_synbasis / V
    if np.linalg.norm(dv0_syn) > 8:
        return None

    # Propagate BCP from pv0 with dv0 for TOF
    T1 = tof_d * 86400.0 / T
    pv_arr = propagate(pv0, t0, [dv0_syn.tolist(), [0, 0, 0], [0, 0, 0]],
                        [T1, 0.0])
    if len(pv_arr) == 0:
        return None

    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return None
    dv2_syn, _ = res
    if not np.all(np.isfinite(dv2_syn)) or np.linalg.norm(dv2_syn) > 5:
        return None

    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0_syn.tolist(), 0.0, 0.0, 0.0, *dv2_syn.tolist(),
            T1, 0.0]
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv2_syn)) * V
    return mass, row, dv_ms


def sweep_two_impulse(udp, idE, idL,
                       raan_grid=None, argp_grid=None, ea_grid=None,
                       t0_grid=None, tof_grid=None):
    """Grid sweep over (raan_e, argp_e, ea_dep, t0, tof) for one pair."""
    if raan_grid is None:
        raan_grid = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    if argp_grid is None:
        argp_grid = (0.0, np.pi)
    if ea_grid is None:
        ea_grid = (0.0, np.pi / 2, np.pi, 3 * np.pi / 2)
    if t0_grid is None:
        t0_grid = (0.0, np.pi)
    if tof_grid is None:
        tof_grid = (4.0, 5.5, 7.0, 9.0, 11.0, 14.0, 18.0)
    best = None
    for raan_e in raan_grid:
        for argp_e in argp_grid:
            for ea_dep in ea_grid:
                for t0_val in t0_grid:
                    for tof_d in tof_grid:
                        res = try_two_impulse(udp, idE, idL, raan_e,
                                                argp_e, ea_dep, t0_val, tof_d)
                        if res is not None and (best is None or res[0] > best[0]):
                            best = res
    return best


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    test_cases = [
        (0, 0, "coplanar LMO"),
        (213, 19, "LEO low-iE + iL=1.07"),
        (303, 109, "LEO + iL=1.08"),
        (244, 105, "LEO + iL=0.50"),
        (21, 200, "LEO + high-eL mid-iL (bank 1095)"),
        (277, 189, "GEO + high-eL (bank 2628)"),
    ]
    print(f"{'pair':>10} {'desc':<35} {'new':>5} {'time':>5}")
    for idE, idL, desc in test_cases:
        t0_start = time.time()
        best = sweep_two_impulse(udp, idE, idL)
        dt = time.time() - t0_start
        if best:
            print(f"  ({idE:>3},{idL:>3}) {desc:<35} {best[0]:>5.0f} {dt:>5.1f}s")
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<35}  FAIL {dt:>5.1f}s")
