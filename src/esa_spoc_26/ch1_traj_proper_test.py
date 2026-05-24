"""Validate Hohmann-quality hypothesis on ONE pair via PROPER Lambert seed.

Frame transforms (nondim, BCP synodic):
- synodic frame rotates at omega=(0,0,1) relative to inertial
- at t=0, synodic and inertial axes align
- Earth at (-mu, 0, 0), Moon at (1-mu, 0, 0) in synodic
- r_inertial(t) = R_z(t) @ r_synodic(t) for the Earth-centered position
- v_inertial = v_synodic + omega × r_earth_centered_synodic   (at fixed t)

Lambert in 2-body Earth-only:
- r0_inertial = r0_earth_centered_synodic (at t=0)
- r1_inertial = R_z(TOF) @ r_target_earth_centered_synodic
- v1 from Lambert gives inertial departure velocity
- dv0 = v1 - v0_inertial, then convert to synodic nondim (same vector / V)
"""
from __future__ import annotations

import time
import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv

MU = CR3BP_MU_EARTH_MOON


def syn_pv_to_inertial_earth_centered(pv_syn, t):
    """Convert synodic state (Earth-centered position via +mu shift) to inertial."""
    x, y, z = pv_syn[0]
    vx, vy, vz = pv_syn[1]
    # Earth-centered synodic position
    r_syn = np.array([x + MU, y, z])
    # Inertial velocity = synodic + omega × r  (omega = (0,0,1) nondim)
    v_syn_inertial_components = np.array([vx - y, vy + (x + MU), vz])
    # Rotate by angle = t (nondim time → radians, since omega=1)
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    r_inertial = R @ r_syn
    v_inertial = R @ v_syn_inertial_components
    return r_inertial * L, v_inertial * V  # SI units


def lambert_dv0(pv0_syn, pv_target_syn, tof):
    """Lambert seed dv0 in synodic nondim units."""
    r0_si, v0_si = syn_pv_to_inertial_earth_centered(pv0_syn, 0.0)
    r1_si, _ = syn_pv_to_inertial_earth_centered(pv_target_syn, tof)
    try:
        lp = pk.lambert_problem(r0_si.tolist(), r1_si.tolist(),
                                 tof * T, MU_EARTH, False, 0)
        v1_inertial = np.array(lp.get_v1()[0])
        dv0_si = v1_inertial - v0_si
        # Synodic dv = inertial dv (instantaneous burn) / V
        return dv0_si / V
    except Exception:
        return None


def solve_pair_proper(udp, idE, idL, tof_d_grid=(4, 5, 6, 8, 10),
                       n_ea_dep=12, n_ea_arr=12, verbose=False):
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]

    best = None
    for tof_d in tof_d_grid:
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, n_ea_dep, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, n_ea_arr, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)

                # Lambert seed
                dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
                if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
                    continue
                # Skip absurd seeds (Lambert can fail silently with huge dv)
                if np.linalg.norm(dv0_seed) > 20:  # > 20*V ≈ 20 km/s
                    continue

                # First: test the pure Lambert seed without DC (open loop)
                pv_arr = propagate(pv0, 0.0, [dv0_seed.tolist(),
                                                [0, 0, 0], [0, 0, 0]],
                                    [tof, 0.0])
                if len(pv_arr) == 0:
                    continue
                dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
                if dv2_res is not None:
                    dv2, _ = dv2_res
                    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
                            *dv0_seed.tolist(), 0.0, 0.0, 0.0,
                            *dv2.tolist(), tof, 0.0]
                    f = udp.fitness(row)[0]
                    if f < 0:
                        mass = -f
                        dv_ms = (np.linalg.norm(dv0_seed) +
                                  np.linalg.norm(dv2)) * V
                        if best is None or mass > best[0]:
                            best = (float(mass), row, float(dv_ms),
                                    float(tof * T * pk.SEC2DAY),
                                    (tof_d, float(ea_dep), float(ea_arr)),
                                    "open_loop")
                            if verbose:
                                print(f"  open ✓ tof={tof_d}d ea=({ea_dep:.2f},"
                                      f"{ea_arr:.2f}): mass={mass:.0f}kg "
                                      f"dv={dv_ms:.0f}m/s", flush=True)
                        continue  # open loop worked, no need for DC

                # DC: drive arrival position to match target (3-D residual,
                # 3 free vars = dv0). Keep TOF and dv1 fixed.
                def residual(p, _pv0=pv0, _tgt=pv_tgt, _tof=tof):
                    pv_a = propagate(_pv0, 0.0, [p.tolist(),
                                                   [0, 0, 0], [0, 0, 0]],
                                      [_tof, 0.0])
                    if len(pv_a) == 0:
                        return [100.0] * 3
                    return [pv_a[0][0] - _tgt[0][0],
                            pv_a[0][1] - _tgt[0][1],
                            pv_a[0][2] - _tgt[0][2]]

                try:
                    sol = least_squares(residual, dv0_seed, method="trf",
                                         xtol=1e-12, ftol=1e-12, max_nfev=50)
                except Exception:
                    continue
                dv0 = sol.x
                pv_arr = propagate(pv0, 0.0, [dv0.tolist(),
                                                [0, 0, 0], [0, 0, 0]],
                                    [tof, 0.0])
                if len(pv_arr) == 0:
                    continue
                dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
                if dv2_res is None:
                    continue
                dv2, _ = dv2_res
                row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
                        *dv0.tolist(), 0.0, 0.0, 0.0,
                        *dv2.tolist(), tof, 0.0]
                f = udp.fitness(row)[0]
                if f < 0:
                    mass = -f
                    dv_ms = (np.linalg.norm(dv0) +
                              np.linalg.norm(dv2)) * V
                    if best is None or mass > best[0]:
                        best = (float(mass), row, float(dv_ms),
                                float(tof * T * pk.SEC2DAY),
                                (tof_d, float(ea_dep), float(ea_arr)),
                                "dc")
                        if verbose:
                            print(f"  dc ✓ tof={tof_d}d ea=({ea_dep:.2f},"
                                  f"{ea_arr:.2f}): mass={mass:.0f}kg "
                                  f"dv={dv_ms:.0f}m/s", flush=True)
    return best


def main():
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    print(f"E0: a={udp.earth_data[0][0]/1e3:.0f} km")
    print(f"L0: a={udp.moon_data[0][0]/1e3:.0f} km")
    print(f"Theoretical Hohmann mass (coplanar circular): ~864 kg")
    print(f"Current bank: 14.82 kg\n")

    t0 = time.time()
    res = solve_pair_proper(udp, 0, 0,
                             tof_d_grid=(4, 5, 6, 8, 10),
                             n_ea_dep=12, n_ea_arr=12, verbose=True)
    dt = time.time() - t0
    if res is None:
        print(f"\nNO valid in {dt:.0f}s")
    else:
        mass, row, dv_ms, dt_d, info, mode = res
        print(f"\nBEST: mass={mass:.0f}kg dv={dv_ms:.0f}m/s dt={dt_d:.1f}d "
              f"({mode}, tof={info[0]}d, ea=({info[1]:.2f},{info[2]:.2f})) "
              f"in {dt:.0f}s")


if __name__ == "__main__":
    main()
