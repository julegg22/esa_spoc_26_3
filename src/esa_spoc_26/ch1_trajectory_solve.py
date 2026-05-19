"""H-002 transfer solver — builds on the official-mirror oracle.

Decomposition (baseline-first 2-impulse, user-approved):
  depart Earth orbit idE (exact, earth_orbit_state)
  → DV0 → coast TOF in BCP → arrival
  → DV2 solved so state2moon == Moon orbit idL within 1e-6 (LOI).

Key constraint surfaced here: SpOC4 Moon orbits are near-circular
(e ~ 1e-7) at a ~ 1.8e6 m, so a feasible arrival must reach lunar
radius |r_M| ≈ aL within the (tiny) eccentricity band — i.e. the
coast must be targeted to the LOI radius; DV2 then only sets the
in-plane circular velocity at inclination iL. `solve_arrival_dv`
returns None when the arrival radius is out of band (shooter's job
to fix), else the minimal corrective DV2.
"""

from __future__ import annotations

import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    CR3BP_MU_EARTH_MOON,
    L,
    MU_MOON,
    V,
    state2moon,
)


def _moon_inertial(posvel):
    """Synodic state → Moon-centred inertial (r,v) SI (state2moon's map,
    pre-ic2par)."""
    [x, y, z], [vx, vy, vz] = posvel
    r = np.array([(x - 1 + CR3BP_MU_EARTH_MOON) * L, y * L, z * L])
    v = np.array([
        (vx - y) * V,
        (vy + x) * V - (1.0 - CR3BP_MU_EARTH_MOON) * V,
        vz * V,
    ])
    return r, v


def solve_arrival_dv(posvel_arr, a_m, e_m, i_m, tol=1e-6):
    """Min-norm synodic DV2 s.t. state2moon(arrival+DV2) == (a_m,e_m,i_m).
    Returns (dv2[3], el) or None if the arrival radius is infeasible for
    this near-circular target (caller must re-target the coast)."""
    r_mf, v_mf = _moon_inertial(posvel_arr)
    r = np.linalg.norm(r_mf)
    if not (a_m * (1 - e_m) - 1.0 <= r <= a_m * (1 + e_m) + 1.0):
        return None  # radius out of perilune/apolune band → shooter fixes

    # vis-viva speed for the target orbit at this radius
    speed = np.sqrt(MU_MOON * (2.0 / r - 1.0 / a_m))
    r_hat = r_mf / r
    # seed: circular-ish velocity ⟂ r in a plane of inclination i_m
    h_dir = np.array([np.sin(i_m), 0.0, np.cos(i_m)])
    t_hat = np.cross(h_dir, r_hat)
    n = np.linalg.norm(t_hat)
    t_hat = t_hat / n if n > 1e-12 else np.array([0.0, 1.0, 0.0])
    v_seed = speed * t_hat

    def resid(v_mf_try):
        el = pk.ic2par(r_mf.tolist(), v_mf_try.tolist(), MU_MOON)
        return [(el[0] - a_m) / L, el[1] - e_m, el[2] - i_m]

    sol = least_squares(resid, v_seed, xtol=1e-14, ftol=1e-14, gtol=1e-14)
    el = pk.ic2par(r_mf.tolist(), sol.x.tolist(), MU_MOON)
    ok = (abs(el[0] - a_m) / L < tol and abs(el[1] - e_m) < tol
          and abs(el[2] - i_m) < tol)
    if not ok:
        return None
    # velocity-only impulse at fixed position: synodic DV2 = Δv_inertial / V
    # (the ±x,y cross-terms and constant offset cancel in the difference)
    dv2 = (sol.x - v_mf) / V
    return dv2, el


if __name__ == "__main__":  # isolation tests
    from esa_spoc_26.ch1_trajectory import LtlTrajectory, moon_orbit_state

    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    aM, eM, iM = udp.moon_data[0]

    # (1) state already exactly on the orbit → DV2 ≈ 0
    pv = moon_orbit_state(aM, eM, iM, 0.3, 0.0, 1.2)
    r = solve_arrival_dv(pv, aM, eM, iM)
    print("on-orbit:", "FAIL" if r is None
          else f"|DV2|={np.linalg.norm(r[0])*V:.3e} m/s (expect ~0), "
               f"match={udp._match_orbit(r[1], aM, eM, iM)}")

    # (2) same position, perturbed velocity → recover corrective DV2
    pv2 = [pv[0], [pv[1][0] + 0.01, pv[1][1] - 0.02, pv[1][2] + 0.005]]
    r = solve_arrival_dv(pv2, aM, eM, iM)
    if r is None:
        print("perturbed: FAIL (no solution)")
    else:
        dv2, _ = r
        fixed = [pv2[0], [pv2[1][0] + dv2[0], pv2[1][1] + dv2[1],
                          pv2[1][2] + dv2[2]]]
        el = state2moon(fixed)
        print(f"perturbed: |DV2|={np.linalg.norm(dv2)*V:.3f} m/s, "
              f"match_after={udp._match_orbit(el, aM, eM, iM)}")
