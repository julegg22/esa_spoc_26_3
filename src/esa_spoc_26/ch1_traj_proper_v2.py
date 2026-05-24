"""Polish: 6-D residual (position + velocity at arrival) + dv0+dv1 DC.

Step 1: Lambert seed for dv0 (zero dv1)
Step 2: 3-D DC on dv0 only to land near Moon orbit (existing approach)
Step 3: 6-D DC with dv0+dv1 → drive arrival to match Moon-orbit (position +
        velocity), making dv2 ≈ 0
Step 4: After grid scan, continuous polish on (ea_dep, ea_arr, TOF) for best IC

Target: ≥800 kg on pair (0,0). Hohmann theoretical 864 kg.
"""
from __future__ import annotations

import time
import numpy as np
import pykep as pk
from scipy.optimize import least_squares, minimize

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv

MU = CR3BP_MU_EARTH_MOON


def syn_pv_to_inertial_earth_centered(pv_syn, t):
    x, y, z = pv_syn[0]
    vx, vy, vz = pv_syn[1]
    r_syn = np.array([x + MU, y, z])
    v_syn_inertial_components = np.array([vx - y, vy + (x + MU), vz])
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    r_inertial = R @ r_syn
    v_inertial = R @ v_syn_inertial_components
    return r_inertial * L, v_inertial * V


def lambert_dv0(pv0_syn, pv_target_syn, tof):
    r0_si, v0_si = syn_pv_to_inertial_earth_centered(pv0_syn, 0.0)
    r1_si, _ = syn_pv_to_inertial_earth_centered(pv_target_syn, tof)
    try:
        lp = pk.lambert_problem(r0_si.tolist(), r1_si.tolist(),
                                 tof * T, MU_EARTH, False, 0)
        v1_inertial = np.array(lp.get_v1()[0])
        return (v1_inertial - v0_si) / V
    except Exception:
        return None


def try_transfer(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                  dc_mode="6d", idE=0, idL=0):
    """Returns (mass, row, dv_ms) or None."""
    dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
        return None
    if np.linalg.norm(dv0_seed) > 15:
        return None

    if dc_mode == "3d":
        # 3-D DC on dv0 only, target position match
        def residual(p, _pv0=pv0, _tgt=pv_tgt, _tof=tof):
            pv_a = propagate(_pv0, 0.0, [p.tolist(), [0, 0, 0], [0, 0, 0]],
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
            return None
        dv0, dv1 = sol.x, np.zeros(3)
        T1, T2 = tof, 0.0

    elif dc_mode == "6d":
        # 6-D DC: dv0+dv1 (6 vars), arrival pos+vel match (6 residuals)
        split = 0.5
        T1 = split * tof
        T2 = (1 - split) * tof

        def residual(p, _pv0=pv0, _tgt=pv_tgt, _T1=T1, _T2=T2):
            dv0 = p[:3].tolist()
            dv1 = p[3:6].tolist()
            pv_a = propagate(_pv0, 0.0, [dv0, dv1, [0, 0, 0]], [_T1, _T2])
            if len(pv_a) == 0:
                return [100.0] * 6
            return [
                pv_a[0][0] - _tgt[0][0],
                pv_a[0][1] - _tgt[0][1],
                pv_a[0][2] - _tgt[0][2],
                pv_a[1][0] - _tgt[1][0],
                pv_a[1][1] - _tgt[1][1],
                pv_a[1][2] - _tgt[1][2],
            ]

        x0 = np.array([*dv0_seed, 0.0, 0.0, 0.0])
        try:
            sol = least_squares(residual, x0, method="trf",
                                 xtol=1e-12, ftol=1e-12, max_nfev=100)
        except Exception:
            return None
        dv0 = sol.x[:3]
        dv1 = sol.x[3:6]

    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
            *dv0.tolist(), *dv1.tolist(), *dv2.tolist(), T1, T2]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
              + np.linalg.norm(dv2)) * V
    return mass, row, dv_ms


def scan_and_polish(udp, idE, idL, tof_grid, n_ea_dep, n_ea_arr,
                      dc_mode="6d", verbose=True):
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    t_start = time.time()
    n_tried = 0
    n_valid = 0
    for tof_d in tof_grid:
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, n_ea_dep, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, n_ea_arr, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                n_tried += 1
                res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                     aL, eL, iL, tof, dc_mode=dc_mode,
                                     idE=idE, idL=idL)
                if res is None:
                    continue
                n_valid += 1
                mass, row, dv_ms = res
                if best is None or mass > best[0]:
                    best = (mass, row, dv_ms, tof_d, ea_dep, ea_arr)
                    if verbose:
                        print(f"  ✓ tof={tof_d}d ea=({ea_dep:.3f},{ea_arr:.3f}):"
                              f" mass={mass:.1f}kg dv={dv_ms:.0f}m/s",
                              flush=True)
    elapsed = time.time() - t_start
    print(f"\n  scanned {n_tried} ICs in {elapsed:.0f}s ({n_valid} valid)",
          flush=True)
    return best


def continuous_polish(udp, idE, idL, best, dc_mode="6d"):
    """Polish (tof, ea_dep, ea_arr) continuously around best grid point."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    _, _, _, tof_d0, ea_d0, ea_a0 = best

    def neg_mass(p):
        tof_d, ea_dep, ea_arr = p
        tof = tof_d * 86400.0 / T
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
        pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
        res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL,
                            tof, dc_mode=dc_mode, idE=idE, idL=idL)
        if res is None:
            return 0.0
        return -res[0]

    x0 = np.array([tof_d0, ea_d0, ea_a0])
    print(f"  polishing around tof={tof_d0}d, ea=({ea_d0:.3f},{ea_a0:.3f})...")
    sol = minimize(neg_mass, x0, method="Nelder-Mead",
                    options={"xatol": 1e-3, "fatol": 0.1,
                              "maxiter": 200, "disp": False,
                              "initial_simplex": np.array([
                                  [tof_d0, ea_d0, ea_a0],
                                  [tof_d0 + 0.5, ea_d0, ea_a0],
                                  [tof_d0, ea_d0 + 0.1, ea_a0],
                                  [tof_d0, ea_d0, ea_a0 + 0.1],
                              ])})
    polished_mass = -sol.fun
    print(f"  polished mass: {polished_mass:.1f}kg "
          f"(was {best[0]:.1f}kg) at tof={sol.x[0]:.2f}d, "
          f"ea=({sol.x[1]:.3f},{sol.x[2]:.3f})")
    return polished_mass, sol.x


def main():
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    print("=" * 60)
    print(f"Pair (0,0): aE={udp.earth_data[0][0]/1e3:.0f}km, "
          f"aL={udp.moon_data[0][0]/1e3:.0f}km")
    print(f"Theoretical Hohmann: ~864 kg, ~3962 m/s")
    print(f"v1 (Lambert+3D DC): 669 kg, 4432 m/s")
    print(f"Target this run: ≥800 kg")
    print("=" * 60)

    print("\n--- 6-D DC scan (16×16×7 = 1792 ICs) ---\n")
    best = scan_and_polish(udp, 0, 0,
                              tof_grid=(3, 4, 5, 6, 7, 8, 10),
                              n_ea_dep=16, n_ea_arr=16,
                              dc_mode="6d", verbose=True)
    if best is None:
        print("\n6-D scan: NO valid")
        return
    print(f"\n6-D best: {best[0]:.1f}kg, dv={best[2]:.0f}m/s, tof={best[3]}d")

    print("\n--- Continuous polish ---\n")
    polished_mass, x_opt = continuous_polish(udp, 0, 0, best, dc_mode="6d")
    print(f"\n*** FINAL: {polished_mass:.1f}kg (gap to Hohmann: {864-polished_mass:.0f}kg) ***")


if __name__ == "__main__":
    main()
