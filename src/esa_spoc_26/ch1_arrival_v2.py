"""Fixed solve_arrival_dv that handles eccentric and inclined Moon orbits.

Bug in v1: rejected arrival if |r - aL| > 384m, then targeted a circular
orbit at r. Only works for eL ≈ 0 Moon orbits where r ≈ aL.

For eccentric Moon orbits (eL up to 0.65), valid arrival radii span
[aL*(1-eL), aL*(1+eL)] — thousands of km wide.

New approach: given arrival position r_mf (3D, Moon-centered inertial)
and arrival velocity v_mf, find dv2 such that the post-burn orbit has
(a, e, i) = (aL, eL, iL). The orbit MUST pass through r_mf, which
constrains:
  |r_mf| ∈ [aL*(1-eL), aL*(1+eL)]

The free knobs for the target orbit are RAAN, argp, true anomaly (3),
and the residual is (a, e, i) match (3) — well-determined.
"""
import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import L, V, MU_MOON


def _moon_inertial(posvel, mu):
    """Synodic state → Moon-centered inertial (r, v) SI."""
    [x, y, z], [vx, vy, vz] = posvel
    r = np.array([(x - 1 + mu) * L, y * L, z * L])
    v = np.array([(vx - y) * V, (vy + x) * V - (1.0 - mu) * V, vz * V])
    return r, v


def solve_arrival_eccentric(posvel_arr, a_m, e_m, i_m, mu=0.01215058439470971,
                             tol=1e-6):
    """Find min-norm dv2 (synodic) so post-burn matches (a_m, e_m, i_m).

    Handles BOTH circular (e_m≈0) and eccentric (e_m up to ~0.65) Moon orbits.

    Returns:
        (dv2_syn[3], el_post) if feasible (radius in orbit's window),
        None otherwise.
    """
    r_mf, v_mf = _moon_inertial(posvel_arr, mu)
    r_norm = np.linalg.norm(r_mf)
    r_min = a_m * (1.0 - e_m)
    r_max = a_m * (1.0 + e_m)
    # Allow small slack: position must be on the orbit, so r ∈ [r_min, r_max]
    # For circular orbits, this is essentially r ≈ a_m.
    if r_norm < r_min - L * tol or r_norm > r_max + L * tol:
        return None  # arrival radius outside orbit's possible range

    # Find velocity direction that puts (r, v) on the target orbit.
    # Initial guess: tangential velocity in the orbit plane.
    # Speed from vis-viva: v² = MU * (2/r - 1/a)
    v_mag = np.sqrt(MU_MOON * (2.0 / r_norm - 1.0 / a_m))

    # Build a target orbit plane normal at inclination i_m
    # Try multiple RAAN candidates; for each, compute valid v direction.
    best_dv2 = None
    best_dv2_norm = np.inf

    # Try several initial v directions: tangential, +/- inclined
    r_hat = r_mf / r_norm
    # In synodic Moon-centered: z-axis is synodic Z
    z_hat = np.array([0.0, 0.0, 1.0])
    # In-plane tangent (perpendicular to r in xy-plane projection)
    rxy = np.array([r_mf[0], r_mf[1], 0.0])
    rxy_n = np.linalg.norm(rxy)
    if rxy_n > 1e-6:
        t_xy = np.array([-r_mf[1], r_mf[0], 0.0]) / rxy_n
    else:
        t_xy = np.array([0.0, 1.0, 0.0])

    # Generate small number of candidate seeds (speed-optimized)
    # First try ± tangential in synodic-XY plane; only add inclined tilts if needed
    def resid(v_try, r=r_mf):
        try:
            el = pk.ic2par(r.tolist(), v_try.tolist(), MU_MOON)
        except Exception:
            return [1e6] * 3
        if not np.all(np.isfinite(el[:3])):
            return [1e6] * 3
        return [(el[0] - a_m) / L, el[1] - e_m, el[2] - i_m]

    def try_seed(seed_v, nfev=80):
        try:
            sol = least_squares(resid, seed_v, method="trf",
                                 xtol=1e-14, ftol=1e-14, max_nfev=nfev)
        except Exception:
            return None
        try:
            el = pk.ic2par(r_mf.tolist(), sol.x.tolist(), MU_MOON)
        except Exception:
            return None
        if (abs(el[0] - a_m) / L < tol and abs(el[1] - e_m) < tol
                and abs(el[2] - i_m) < tol):
            return sol.x
        return None

    # Seeds: v_mf (on-orbit shortcut) + ± × full tilt range [0, i_m] (4-point grid)
    seeds = [v_mf]
    if i_m > 1e-6:
        tilts = np.linspace(0.0, i_m, 4)
    else:
        tilts = [0.0]
    for sign in (1, -1):
        for tilt in tilts:
            if abs(tilt) < 1e-10:
                seeds.append(sign * v_mag * t_xy)
            else:
                c, s = np.cos(tilt), np.sin(tilt)
                t_rot = (t_xy * c + np.cross(r_hat, t_xy) * s
                         + r_hat * np.dot(r_hat, t_xy) * (1 - c))
                tn = np.linalg.norm(t_rot)
                if tn > 1e-12:
                    seeds.append(sign * v_mag * t_rot / tn)

    for seed_v in seeds:
        v_found = try_seed(seed_v)
        if v_found is not None:
            dv2 = (v_found - v_mf) / V
            if np.linalg.norm(dv2) < best_dv2_norm:
                best_dv2 = dv2
                best_dv2_norm = np.linalg.norm(dv2)

    if best_dv2 is None:
        return None
    return best_dv2, None  # Return None for el to match original API


if __name__ == "__main__":
    # Sanity test
    from esa_spoc_26.ch1_trajectory import (
        LtlTrajectory, moon_orbit_state,
    )
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # Test 1: on-orbit point should give dv2 ≈ 0
    print("Test 1: on-orbit point → dv2 ≈ 0")
    for idL in [0, 17, 116, 181, 234]:
        aL, eL, iL = udp.moon_data[idL]
        pv = moon_orbit_state(aL, eL, iL, 0.3, 0.0, 1.2)
        res = solve_arrival_eccentric(pv, aL, eL, iL)
        if res is None:
            print(f"  L{idL} (eL={eL:.3f}): FAIL (None)")
        else:
            dv2, _ = res
            print(f"  L{idL} (eL={eL:.3f}): |dv2|={np.linalg.norm(dv2)*V:.4e} m/s")

    # Test 2: same position, perturbed velocity
    print("\nTest 2: perturbed velocity recovers")
    for idL in [0, 181]:
        aL, eL, iL = udp.moon_data[idL]
        pv = moon_orbit_state(aL, eL, iL, 0.0, 0.0, 1.5)
        pv2 = [pv[0], [pv[1][0] + 0.05, pv[1][1] - 0.05, pv[1][2] + 0.01]]
        res = solve_arrival_eccentric(pv2, aL, eL, iL)
        if res is None:
            print(f"  L{idL} (eL={eL:.3f}): FAIL")
        else:
            dv2, _ = res
            print(f"  L{idL} (eL={eL:.3f}): |dv2|={np.linalg.norm(dv2)*V:.1f} m/s")

    # Test 3: arrival away from aL (only valid for eccentric)
    print("\nTest 3: arrival at non-aL radius (eccentric only)")
    for idL in [181, 234, 0]:
        aL, eL, iL = udp.moon_data[idL]
        # Try arrival at half-window
        r_test = aL * (1 - eL * 0.5)
        # Build state at this radius in xy plane (i=iL doesn't matter for this test)
        pv = [[(r_test / L) - 0.01215 + 1.0, 0.0, 0.0],
               [0.0, 0.001, 0.0]]
        res = solve_arrival_eccentric(pv, aL, eL, iL)
        if res is None:
            print(f"  L{idL} (eL={eL:.3f}, r_test={r_test/1e3:.0f}km): FAIL")
        else:
            dv2, _ = res
            print(f"  L{idL} (eL={eL:.3f}, r_test={r_test/1e3:.0f}km): "
                  f"|dv2|={np.linalg.norm(dv2)*V:.1f} m/s")
