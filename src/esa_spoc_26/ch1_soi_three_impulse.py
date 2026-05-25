"""Plane-change-at-SOI 3-impulse solver.

Standard mission design pattern (Wiesel §6.5, Vallado §11.4):
- LEO+inclined-Moon pairs naively burn 1500+ m/s extra at LEO velocity
  for plane change. Putting plane change at LUNAR SOI (where v~800 m/s)
  costs 5-10× less.

Architecture:
1. pv0 = earth_orbit_state(aE, eE, iE, raan_e=0, argp_e=0, ea_dep)
2. dv0 = Lambert-coplanar from pv0 to a target IN synodic XY plane near Moon
   (specifically: the line where Moon's orbit-plane intersects synodic XY)
3. propagate T1 to SOI (Earth-side Lambert TOF)
4. dv1 = plane-change burn (rotates velocity into Moon-orbit plane)
5. propagate T2 (short, captures into Moon orbit)
6. dv2 = circularization at apoapsis (small)

The KEY new piece: dv0 stays IN PLANE; dv1 does the plane change at low v.

For coplanar pairs (iL ≈ 0), dv1 → 0 and the solver degenerates to
standard 2-impulse.
"""
import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_SOI = 66200e3 / L  # nondim


def _syn_to_inertial_earth(pv_syn, t):
    """Synodic state → Earth-centered inertial (SI m, m/s)."""
    x, y, z = pv_syn[0]
    vx, vy, vz = pv_syn[1]
    r_syn = np.array([x + MU, y, z])
    v_syn_inertial = np.array([vx - y, vy + (x + MU), vz])
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return R @ r_syn * L, R @ v_syn_inertial * V


def _moon_pos_inertial(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([(1 - MU) * c, (1 - MU) * s, 0.0]) * L


def lambert_coplanar_to_soi(pv0_syn, t_arr_syn, tof_nondim):
    """Lambert from pv0 (synodic) to a coplanar SOI entry point.

    The SOI entry point is in synodic XY plane at distance R_SOI from
    Moon center, on the Moon-Earth line.

    Returns dv0 (synodic nondim), or None.
    """
    r0_si, v0_si = _syn_to_inertial_earth(pv0_syn, 0.0)
    # Moon position at arrival in inertial:
    moon_pos = _moon_pos_inertial(t_arr_syn)
    # SOI entry direction: from Moon toward Earth (in inertial), staying in z=0
    moon_dir = moon_pos[:2]
    moon_dir_unit = moon_dir / np.linalg.norm(moon_dir)
    # SOI entry point: R_SOI * L toward Earth, z=0 (in XY plane)
    soi_entry = np.array([moon_pos[0] - moon_dir_unit[0] * R_SOI * L,
                           moon_pos[1] - moon_dir_unit[1] * R_SOI * L,
                           0.0])

    try:
        lp = pk.lambert_problem(r0_si.tolist(), soi_entry.tolist(),
                                  tof_nondim * T, MU_EARTH, False, 0)
        v1 = np.array(lp.get_v1()[0])
        dv0_si = v1 - v0_si
    except Exception:
        return None, None
    if not np.all(np.isfinite(dv0_si)):
        return None, None
    return dv0_si / V, soi_entry


def try_3impulse_soi(udp, idE, idL, ea_dep, ea_arr, tof_earth_d, tof_moon_d,
                       raan_e=0.0, argp_e=0.0, raan_l=0.0, argp_l=0.0):
    """Build SOI-handoff 3-impulse trajectory + BCP DC.

    Returns (mass, row, dv_ms) or None.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)

    tof_earth = tof_earth_d * 86400.0 / T  # nondim
    tof_moon = tof_moon_d * 86400.0 / T

    # Step 1: Lambert in plane to SOI entry
    dv0_syn, soi_entry = lambert_coplanar_to_soi(pv0, tof_earth, tof_earth)
    if dv0_syn is None or np.linalg.norm(dv0_syn) > 10:
        return None

    # Step 2: Propagate in BCP with dv0
    pv_at_soi = propagate(pv0, 0.0, [dv0_syn.tolist(), [0, 0, 0], [0, 0, 0]],
                           [tof_earth, 0.0])
    if len(pv_at_soi) == 0:
        return None

    # Step 3: DC on dv1 to match arrival position (3 vars, 3 residuals)
    # pv1 = pv_at_soi + dv1, propagated T2 → arrival should = pv_tgt position
    def residual(dv1):
        pv_arr = propagate(pv_at_soi, tof_earth,
                            [[0, 0, 0], dv1.tolist(), [0, 0, 0]],
                            [0.0, tof_moon])
        if len(pv_arr) == 0:
            return [100.0] * 3
        return [pv_arr[0][0] - pv_tgt[0][0],
                pv_arr[0][1] - pv_tgt[0][1],
                pv_arr[0][2] - pv_tgt[0][2]]

    # Initial guess for dv1: plane-change velocity vector
    # Current velocity at SOI in inertial: v_soi_inertial
    # Desired direction: rotate to be in Moon orbit plane
    dv1_seed = np.zeros(3)
    try:
        sol = least_squares(residual, dv1_seed, method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=50)
    except Exception:
        return None
    dv1_syn = sol.x

    # Step 4: Propagate post-dv1
    pv_arr = propagate(pv_at_soi, tof_earth,
                        [[0, 0, 0], dv1_syn.tolist(), [0, 0, 0]],
                        [0.0, tof_moon])
    if len(pv_arr) == 0:
        return None

    # Step 5: dv2 = circularize
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2_syn, _ = dv2_res

    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
            *dv0_syn.tolist(), *dv1_syn.tolist(), *dv2_syn.tolist(),
            tof_earth, tof_moon]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv1_syn)
              + np.linalg.norm(dv2_syn)) * V
    return mass, row, dv_ms


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # Test on a LEO + inclined Moon pair that gave only 5 kg before
    # E213 (LEO, iE=0.20) → L19 (aL=1.90, iL=1.07) gave dv0=4792, dv2=2199, mass=5
    test_cases = [
        (213, 19, "Worst case LEO+inclined"),
        (303, 109, "LEO + iL=1.08"),
        (227, 315, "LEO+iE=0.41 + iL=0.47"),
        (244, 105, "LEO+iE=0.34 + iL=0.50"),
        (0, 0, "Coplanar control"),
    ]

    print("Testing plane-change-at-SOI 3-impulse solver:", flush=True)
    print(f"{'pair':>10} {'desc':<25} {'mass':>5} {'dv0':>5} {'dv1':>4} {'dv2':>5} {'tot':>5}",
          flush=True)
    for idE, idL, desc in test_cases:
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        best = None
        t_start = time.time()
        # Scan ea_dep × ea_arr × tof_earth × tof_moon
        for tof_e in (4, 6, 8):
            for tof_m in (1, 2, 3):
                for ea_dep in np.linspace(0, 2*np.pi, 6, endpoint=False):
                    for ea_arr in np.linspace(0, 2*np.pi, 6, endpoint=False):
                        res = try_3impulse_soi(udp, idE, idL, ea_dep, ea_arr,
                                                  tof_e, tof_m)
                        if res is not None:
                            if best is None or res[0] > best[0]:
                                best = res
        dt = time.time() - t_start
        if best:
            mass, row, dv_tot = best
            dv0 = np.sqrt(row[10]**2+row[11]**2+row[12]**2) * V
            dv1 = np.sqrt(row[13]**2+row[14]**2+row[15]**2) * V
            dv2 = np.sqrt(row[16]**2+row[17]**2+row[18]**2) * V
            print(f"  ({idE:>3},{idL:>3}) {desc:<25} {mass:>5.0f} "
                  f"{dv0:>5.0f} {dv1:>4.0f} {dv2:>5.0f} {dv_tot:>5.0f} "
                  f"({dt:.0f}s)", flush=True)
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<25} FAIL ({dt:.0f}s)",
                  flush=True)
