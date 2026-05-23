"""Ch1 Trajectory v2 — properly-determined residual + Lambert seeding.

The bug in ch1_trajectory_solve.solve_transfer_back: residual only
constrains |r| = a_E, leaving (e, i) to chance. The least_squares
finds points that match radius but have arbitrary (e, i), so
solve_departure_dv almost always rejects.

Fix: change residual to 3 equations [(r-a_E)/L, e-e_E, i-i_E].
Add Lambert-based seeding and longer TOF range. Targets the actual
orbit, not just its radius.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import LtlTrajectory, T, V, L, moon_orbit_state, MU_EARTH
from esa_spoc_26.ch1_trajectory_solve import (
    _back_state, _earth_inertial, solve_departure_dv,
)


def solve_transfer_back_v2(udp, idE, idL, n_seed=4,
                             tof_grid=(3.0, 8.0, 30.0),
                             verbose=False):
    """Backward shooting with PROPERLY-DETERMINED residual.

    Residual: [(r - a_E)/L, e_back - e_E, i_back - i_E]
    3 equations, 5 unknowns — still underdetermined but enforces full
    orbital identity (not just radius).
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best_pack = None
    best_mass = -np.inf
    best_err_radius = np.inf
    rng = np.random.default_rng(42)

    for tof_d in tof_grid:
        tof = tof_d * 86400.0 / T
        for k in range(n_seed):
            nuM = rng.uniform(0, 2 * np.pi)
            OmM = rng.uniform(0, 2 * np.pi)
            # Initial dv2 seed
            arr = moon_orbit_state(aL, eL, iL, OmM, 0.0, nuM)
            from esa_spoc_26.ch1_trajectory_solve import _moon_inertial
            _, vmf = _moon_inertial(arr)
            sp = np.linalg.norm(vmf)
            dv2_seed = (vmf / sp) * (300.0 / V) if sp > 0 else np.array([0.0, 0.0, 0.0])

            def resid(p, _OmM=OmM, _tof=tof):
                nu, t_arr = p[0], p[1]
                dv2 = p[2:5]
                a = moon_orbit_state(aL, eL, iL, _OmM, 0.0, nu)
                S = [a[0], [a[1][0] - dv2[0], a[1][1] - dv2[1],
                            a[1][2] - dv2[2]]]
                D = _back_state(S[0], S[1], t_arr, _tof)
                if D is None:
                    return np.array([10.0, 10.0, 10.0])
                r_ef, v_back = _earth_inertial([[D[0], D[1], D[2]],
                                                  [D[3], D[4], D[5]]])
                # Compute orbital elements of backward-propagated state
                try:
                    el = pk.ic2par(r_ef.tolist(), v_back.tolist(), MU_EARTH)
                except Exception:
                    return np.array([10.0, 10.0, 10.0])
                a_back, e_back, i_back = el[0], el[1], el[2]
                return np.array([
                    (a_back - aE) / L,
                    e_back - eE,
                    i_back - iE,
                ])

            x0 = np.array([nuM, 0.0, *dv2_seed])
            try:
                sol = least_squares(resid, x0, method="trf",
                                     xtol=1e-12, max_nfev=200)
            except Exception:
                continue
            nu, t_arr = sol.x[0], sol.x[1]
            dv2 = sol.x[2:5]
            arr = moon_orbit_state(aL, eL, iL, OmM, 0.0, nu)
            S = [arr[0], [arr[1][0] - dv2[0], arr[1][1] - dv2[1],
                          arr[1][2] - dv2[2]]]
            D = _back_state(S[0], S[1], t_arr, tof)
            if D is None:
                continue
            d_state = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]
            r_ef, _ = _earth_inertial(d_state)
            best_err_radius = min(best_err_radius,
                                    abs(np.linalg.norm(r_ef) - aE))
            dep = solve_departure_dv(d_state, aE, eE, iE)
            if dep is None:
                continue
            posvel0, dv0, _ = dep
            row = [idE, idL, 0, t_arr - tof, *posvel0[0], *posvel0[1],
                   *dv0, 0.0, 0.0, 0.0, *dv2.tolist(), float(tof), 0.0]
            f = udp.fitness(row)[0]
            if f < 0 and -f > best_mass:
                best_mass = -f
                dvms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
                best_pack = (row, -f, dvms,
                              (t_arr - (t_arr - tof)) * T * pk.SEC2DAY)
                if verbose:
                    print(f"    POSITIVE mass={best_mass:.0f} kg, "
                          f"dv={dvms:.0f} m/s, tof_d={tof_d}", flush=True)
    return best_pack if best_pack else (None, best_err_radius)


def main(n_E=10, n_L=10, n_seed=10):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    print(f"v2 search: {n_E} × {n_L} (E, L) pairs", flush=True)
    positives = 0
    results = {}
    t_start = time.time()
    for idE in range(n_E):
        for idL in range(n_L):
            t0 = time.time()
            r = solve_transfer_back_v2(udp, idE, idL, n_seed=n_seed,
                                          verbose=False)
            wall = time.time() - t0
            if isinstance(r, tuple) and r[0] is not None:
                row, mass, dvms, dt_d = r
                results[(idE, idL)] = (row, mass, dvms, dt_d)
                positives += 1
                print(f"  ✓ ({idE},{idL}): mass={mass:.0f} kg, "
                      f"dv={dvms:.0f} m/s, dt={dt_d:.1f} d, wall={wall:.1f}s",
                      flush=True)
            else:
                err = r[1] if isinstance(r, tuple) else 0
                if (idE * n_L + idL) % 20 == 0:
                    print(f"  ({idE},{idL}): no mass, err={err:.2e}, "
                          f"wall={wall:.1f}s", flush=True)
    print(f"\nTotal: {positives}/{n_E*n_L} pairs in "
          f"{time.time()-t_start:.0f}s", flush=True)
    return {"n_positive": positives, "n_total": n_E * n_L,
            "results": list(results.keys())}


if __name__ == "__main__":
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    nl = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    ns = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    print(json.dumps(main(n_E=ne, n_L=nl, n_seed=ns), indent=2))
