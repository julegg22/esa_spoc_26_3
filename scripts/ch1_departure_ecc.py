"""E-701: eccentric-aware Earth-side departure solver — the mirror of solve_arrival_dv.

BUG FOUND: the library solve_departure_dv builds a CIRCULAR departure orbit (resid targets el[1]->0,
el[0]->r) and checks |el[1]-e_e|<1e-6. Since 399/400 Earth orbits are eccentric (e up to 0.74), it
can NEVER validate them — every backward-shot official check was doomed regardless of corrector quality.
This is the exact analog of the 2026-05-24 arrival-side fix (solve_arrival_dv) that was applied to the
Moon end but NEVER mirrored to the Earth end.

Correct condition (raan/argp/nu FREE per the validator): departure POSITION radius in
[a_e(1-e_e), a_e(1+e_e)]; the Earth-orbit velocity is then solved so (r_ef,v_orb)=(a_e,e_e,i_e), and
dv0 = v_transfer - v_orb. Window is +-a_e*e_e (km-scale), not 384 m — so no STM corrector is needed
for the eccentric majority; the radius just has to land in the band."""
import sys, numpy as np
import pykep as pk
from scipy.optimize import least_squares
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory_solve import _earth_inertial
from esa_spoc_26.ch1_trajectory import CR3BP_MU_EARTH_MOON, MU_EARTH, L, V


def solve_departure_dv_ecc(d_state, a_e, e_e, i_e, tol=1e-6):
    """Eccentric Earth-side mirror of solve_arrival_dv. Returns (posvel0, dv0[3], el) or None."""
    r_ef, v_cur = _earth_inertial(d_state)        # v_cur = transfer velocity at departure
    r = np.linalg.norm(r_ef)
    r_min, r_max = a_e * (1.0 - e_e), a_e * (1.0 + e_e)
    if r < r_min - L * tol or r > r_max + L * tol:
        return None
    v_mag_seed = np.sqrt(max(MU_EARTH * (2.0 / r - 1.0 / a_e), 1.0))
    r_hat = r_ef / r
    rxy = np.array([r_ef[0], r_ef[1], 0.0]); rxy_n = np.linalg.norm(rxy)
    t_xy = (np.array([-r_ef[1], r_ef[0], 0.0]) / rxy_n if rxy_n > 1e-6 else np.array([0.0, 1.0, 0.0]))

    def resid(v):
        el = pk.ic2par(r_ef.tolist(), v.tolist(), MU_EARTH)
        if not np.all(np.isfinite(el[:3])):
            return [1e6] * 3
        return [(el[0] - a_e) / L, el[1] - e_e, el[2] - i_e]

    seeds = []
    tilts = [0.0] if i_e < 0.01 else [0.0, i_e, -i_e]
    for sign in (1, -1):
        for tilt in tilts:
            c, s = np.cos(tilt), np.sin(tilt)
            t_rot = (t_xy * c + np.cross(r_hat, t_xy) * s + r_hat * np.dot(r_hat, t_xy) * (1 - c))
            tn = np.linalg.norm(t_rot)
            if tn > 1e-12:
                seeds.append(sign * v_mag_seed * t_rot / tn)
    best = None; best_norm = np.inf; best_el = None
    for v_seed in seeds:
        try:
            sol = least_squares(resid, v_seed, xtol=1e-12, ftol=1e-12, max_nfev=50)
            el = pk.ic2par(r_ef.tolist(), sol.x.tolist(), MU_EARTH)
        except Exception:
            continue
        if (abs(el[0] - a_e) / L < tol and abs(el[1] - e_e) < tol and abs(el[2] - i_e) < tol):
            dv0 = (v_cur - sol.x) / V
            if np.linalg.norm(dv0) < best_norm:
                best, best_norm, best_el = sol.x, np.linalg.norm(dv0), el
    if best is None:
        return None
    mu = CR3BP_MU_EARTH_MOON
    x, y, z = r_ef / L; x -= mu
    v_orb = [best[0] / V + y, best[1] / V - mu - x, best[2] / V]
    posvel0 = [[x, y, z], v_orb]
    dv0 = ((v_cur - best) / V).tolist()
    return posvel0, dv0, best_el
