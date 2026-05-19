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
from scipy.optimize import least_squares, minimize_scalar

from esa_spoc_26.ch1_trajectory import (
    CR3BP_MU_EARTH_MOON,
    MU_EARTH,
    MU_MOON,
    L,
    T,
    V,
    earth_orbit_state,
    moon_orbit_state,
    propagate,
    state2moon,
)


def _earth_inertial(posvel):
    """Synodic state → Earth-centred inertial (r,v) SI (state2earth's map)."""
    [x, y, z], [vx, vy, vz] = posvel
    r = np.array([(x + CR3BP_MU_EARTH_MOON) * L, y * L, z * L])
    v = np.array([
        (vx - y) * V,
        (vy + x) * V + CR3BP_MU_EARTH_MOON * V,
        vz * V,
    ])
    return r, v


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
    """Min-norm synodic DV2 so the official `_match_orbit(a_m,e_m,i_m)`
    passes. Key: the official a-tolerance is L·tol (≈384 m), so if the
    arrival radius r is within that of a_m, a **circular** orbit at
    radius r with inclination i_m is accepted (a'=r within tol of a_m;
    e'≈0 within tol of e_m~1e-7; i'=i_m). We target that achievable
    orbit, then validate against the official target. Returns
    (dv2[3], el) or None if r is outside the a-tolerance."""
    r_mf, v_mf = _moon_inertial(posvel_arr)
    r = np.linalg.norm(r_mf)
    if abs(r - a_m) >= L * tol:
        return None  # radius outside the official a-tolerance → coast fixes

    speed = np.sqrt(MU_MOON / r)  # circular at the achieved radius
    r_hat = r_mf / r
    h_dir = np.array([np.sin(i_m), 0.0, np.cos(i_m)])
    t_hat = np.cross(h_dir, r_hat)
    n = np.linalg.norm(t_hat)
    t_hat = t_hat / n if n > 1e-12 else np.array([0.0, 1.0, 0.0])
    v_seed = speed * t_hat

    # target the *achievable* circular orbit (a=r, e=0, i=i_m)
    def resid(v_mf_try):
        el = pk.ic2par(r_mf.tolist(), v_mf_try.tolist(), MU_MOON)
        return [(el[0] - r) / L, el[1], el[2] - i_m]

    sol = least_squares(resid, v_seed, xtol=1e-14, ftol=1e-14, gtol=1e-14)
    el = pk.ic2par(r_mf.tolist(), sol.x.tolist(), MU_MOON)
    # validate against the OFFICIAL target (a_m, e_m, i_m)
    ok = (abs(el[0] - a_m) / L < tol and abs(el[1] - e_m) < tol
          and abs(el[2] - i_m) < tol)
    if not ok:
        return None
    # velocity-only impulse at fixed position: synodic DV2 = Δv_inertial / V
    dv2 = (sol.x - v_mf) / V
    return dv2, el


def solve_departure_dv(d_state, a_e, e_e, i_e, tol=1e-6):
    """Earth-side mirror of solve_arrival_dv. Given a backward-shot
    departure-side state, build the on-Earth-orbit `posvel0` (circular
    at the achieved radius, incl i_e — within the official 384 m a-tol)
    and the burn DV0 the official forward propagate must apply.
    Returns (posvel0, dv0[3], el) or None if radius out of a-tol."""
    r_ef, v_cur = _earth_inertial(d_state)
    r = np.linalg.norm(r_ef)
    if abs(r - a_e) >= L * tol:
        return None
    speed = np.sqrt(MU_EARTH / r)
    r_hat = r_ef / r
    h_dir = np.array([np.sin(i_e), 0.0, np.cos(i_e)])
    t_hat = np.cross(h_dir, r_hat)
    nn = np.linalg.norm(t_hat)
    t_hat = t_hat / nn if nn > 1e-12 else np.array([0.0, 1.0, 0.0])
    v_seed = speed * t_hat

    def resid(vv):
        el = pk.ic2par(r_ef.tolist(), vv.tolist(), MU_EARTH)
        return [(el[0] - r) / L, el[1], el[2] - i_e]

    sol = least_squares(resid, v_seed, xtol=1e-14, ftol=1e-14, gtol=1e-14)
    el = pk.ic2par(r_ef.tolist(), sol.x.tolist(), MU_EARTH)
    if not (abs(el[0] - a_e) / L < tol and abs(el[1] - e_e) < tol
            and abs(el[2] - i_e) < tol):
        return None
    mu = CR3BP_MU_EARTH_MOON
    x, y, z = r_ef / L
    x -= mu
    vo = sol.x  # circular orbit inertial velocity
    pos = [x, y, z]
    v_orb = [vo[0] / V + y, vo[1] / V - mu - x, vo[2] / V]
    posvel0 = [pos, v_orb]
    dv0 = ((v_cur - sol.x) / V).tolist()  # forward burn = D.v − orbit.v
    return posvel0, dv0, el


def _back_state(arr_pos, v_pre, t_arr, tof):
    """Backward-propagate the BCP from (arr_pos, v_pre) at t_arr for
    `tof` (to t_arr−tof). Returns the departure-side 6-state or None."""
    ta = _ta()
    ta.time = t_arr
    ta.state[:] = [arr_pos[0], arr_pos[1], arr_pos[2],
                   v_pre[0], v_pre[1], v_pre[2]]
    try:
        ta.propagate_until(t_arr - tof)
    except Exception:
        return None
    return ta.state.copy()


def _r_moon(posvel):
    r, _ = _moon_inertial(posvel)
    return np.linalg.norm(r)


_TA = None  # cached BCP integrator (avoid per-call rebuild; ~100× faster)


def _ta():
    global _TA
    if _TA is None:
        import heyoka as hy

        from esa_spoc_26.ch1_trajectory import (
            BCP_MU_S,
            BCP_OMEGA_S,
            BCP_RHO_S,
            bcp_dyn,
        )

        # MUST match the official scorer's tol (1e-16): over a multi-day
        # sensitive 3-body arc a looser tol diverges >> the 384 m
        # a-tolerance, so the DC would optimise a trajectory the scorer
        # never sees (E-008 failure mode; see C-005 sensitivity caveat).
        _TA = hy.taylor_adaptive(bcp_dyn(), [0.0] * 6, tol=1e-16)
        _TA.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
    return _TA


_MU = CR3BP_MU_EARTH_MOON
_RE2 = ((6378137.0 + 99000.0) / L) ** 2     # Earth keep-out (R⊕+99 km)
_RM2 = ((1737400.0 + 30000.0) / L) ** 2     # Moon keep-out (R☾+30 km)


def _state_at(pv0, t0, dv0, trel):
    """Reset the cached integrator to the post-DV0 state and propagate
    to t0+trel; return the 6-state (or None on integration failure)."""
    ta = _ta()
    ta.time = t0
    ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                   pv0[1][0] + dv0[0], pv0[1][1] + dv0[1],
                   pv0[1][2] + dv0[2]]
    try:
        ta.propagate_until(t0 + max(trel, 0.0))
    except Exception:
        return None
    return ta.state.copy()


def _rm_nd(s):
    return np.sqrt((s[0] - (1 - _MU)) ** 2 + s[1] ** 2 + s[2] ** 2)


def track_to_perilune(pv0, t0, dv0, tmax, n=3000):
    """Closest lunar approach. Cheap *incremental* fine sweep (one
    continuous integration) to bracket the perilune, then parabolic
    vertex interpolation + one exact re-integration (sub-metre).
    Returns (t_peri, state6, r_peri_m, impacted)."""
    ta = _ta()
    ta.time = t0
    ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                   pv0[1][0] + dv0[0], pv0[1][1] + dv0[1],
                   pv0[1][2] + dv0[2]]
    dt = tmax / n
    best_d, best_k, best_s = np.inf, 1, ta.state.copy()
    for k in range(1, n + 1):
        try:
            ta.propagate_until(t0 + k * dt)
        except Exception:
            return best_k * dt, best_s, best_d * L, True
        x, y, z = ta.state[0], ta.state[1], ta.state[2]
        if (x + _MU) ** 2 + y * y + z * z < _RE2:
            return best_k * dt, best_s, best_d * L, True
        if (x - (1 - _MU)) ** 2 + y * y + z * z < _RM2:
            return best_k * dt, best_s, best_d * L, True
        d = np.sqrt((x - (1 - _MU)) ** 2 + y * y + z * z)
        if d < best_d:
            best_d, best_k, best_s = d, k, ta.state.copy()
    # parabolic vertex from the 3 samples bracketing the discrete min
    if 1 < best_k < n:
        sm = _state_at(pv0, t0, dv0, (best_k - 1) * dt)
        sp = _state_at(pv0, t0, dv0, (best_k + 1) * dt)
        if sm is not None and sp is not None:
            rm, r0, rp = _rm_nd(sm), best_d, _rm_nd(sp)
            den = rm - 2 * r0 + rp
            if abs(den) > 1e-18:
                frac = 0.5 * (rm - rp) / den  # vertex offset in [-1,1]·dt
                t_star = (best_k + np.clip(frac, -1.0, 1.0)) * dt
                sv = _state_at(pv0, t0, dv0, t_star)
                if sv is not None and _rm_nd(sv) < best_d:
                    return t_star, sv, _rm_nd(sv) * L, False
    return best_k * dt, best_s, best_d * L, False


def solve_transfer_dc(udp, idE, idL, n_ea=6, t0_grid=(0.0, np.pi)):
    """Differential-corrected 2-impulse transfer (C-005). Patched-conic
    seed → least_squares on [DV0(3), TOF] driving the closest lunar
    approach to aL → DV2 via solve_arrival_dv. Multi-start over the
    Earth-departure phase and the Sun phase t0. Returns the best valid
    (row21, mass, dv_ms, dt_d) or (None, best_min_dist_err_m)."""
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    D = L
    best_row, best_mass, best_err = None, -1.0, np.inf

    # Moon centre in the state2earth Earth-centred frame: x_EF=(x+μ)L,
    # synodic Moon x=1−μ ⇒ Moon centre at (L, 0, 0).
    moon_ctr = np.array([D, 0.0, 0.0])

    for ea in np.linspace(0.0, 2 * np.pi, n_ea, endpoint=False):
        r0, v0 = pk.par2ic([aE, eE, iE, 0.0, 0.0, ea], MU_EARTH)
        r0 = np.array(r0)
        v0 = np.array(v0)
        r0n = np.linalg.norm(r0)
        a_t = 0.5 * (r0n + D)
        tof_seed = np.pi * np.sqrt(a_t**3 / MU_EARTH) / T  # Hohmann ½-period
        # Lambert (Earth two-body) departure→Moon vicinity: proper v1
        # aimed at the lunar geometry (E-009 fix: patched-conic seed was
        # only a prograde kick → hyperbolic arrival).
        dv0_seed = None
        try:
            lp = pk.lambert_problem(r0.tolist(), moon_ctr.tolist(),
                                    tof_seed * T, MU_EARTH, False, 0)
            v1 = np.array(lp.get_v1()[0])
            cand = (v1 - v0) / V
            if np.all(np.isfinite(cand)):
                dv0_seed = cand
        except Exception:
            dv0_seed = None
        if dv0_seed is None:  # 180°-singular Lambert / failure → patched-conic
            vhat = v0 / np.linalg.norm(v0)
            v_peri = np.sqrt(MU_EARTH * (2.0 / r0n - 1.0 / a_t))
            dv0_seed = (v_peri * vhat - v0) / V
        if not np.all(np.isfinite(dv0_seed)):
            continue  # degenerate departure geometry — skip this phase
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea)

        v_circ = np.sqrt(MU_MOON / aM)  # target speed at LLO radius

        for t0 in t0_grid:
            def resid(p, _pv0=pv0, _t0=t0, _vc=v_circ):
                _, s, dmin, imp = track_to_perilune(
                    _pv0, _t0, p[:3], max(p[3], 0.05))
                if imp or s is None:
                    return [10.0, 10.0]
                _, v_mf = _moon_inertial([[s[0], s[1], s[2]],
                                          [s[3], s[4], s[5]]])
                # (a) hit LLO radius, (b) arrive at circular speed so
                # the LOI burn (DV2) collapses to near-zero (E-008).
                return [(dmin - aM) / L,
                        (np.linalg.norm(v_mf) - _vc) / _vc]

            x0 = np.array([*dv0_seed, tof_seed])
            sol = least_squares(resid, x0, method="trf",
                                xtol=1e-10, max_nfev=60)
            dv0 = sol.x[:3]
            tcl, _s, dmin, imp = track_to_perilune(
                pv0, t0, dv0, max(sol.x[3], 0.05))
            best_err = min(best_err, abs(dmin - aM))
            if imp or abs(dmin - aM) > aM * 1e-3:
                continue

            # consistency: localise T1 with the OFFICIAL propagate
            # (tol 1e-16) — the scorer's truth, not the fast tracker.
            def off_err(t1, _dv0=dv0, _t0=t0, _pv0=pv0):
                pv = propagate(_pv0, _t0, [list(_dv0), [0, 0, 0],
                                           [0, 0, 0]], [max(t1, 1e-4), 0.0])
                return np.inf if len(pv) == 0 else abs(_r_moon(pv) - aM)

            ts = np.linspace(0.6 * tcl, 1.4 * tcl, 25)
            t1 = min(ts, key=off_err)
            r1 = minimize_scalar(
                off_err, bracket=(0.92 * t1, t1, 1.08 * t1),
                method="brent", options={"xtol": 1e-9, "maxiter": 40})
            t1 = max(r1.x, 1e-4)
            pv_off = propagate(pv0, t0, [list(dv0), [0, 0, 0], [0, 0, 0]],
                               [t1, 0.0])
            if len(pv_off) == 0 or abs(_r_moon(pv_off) - aM) > aM * 1e-3:
                continue
            dvr = solve_arrival_dv(pv_off, aM, eM, iM)
            if dvr is None:
                continue
            dv2, _ = dvr
            tcl = t1
            dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
            row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
                   *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(),
                   float(tcl), 0.0]
            f = udp.fitness(row)[0]
            if f < 0 and -f > best_mass:
                best_mass = -f
                best_row = row
                dt_d = tcl * T * pk.SEC2DAY
                best_pack = (row, -f, dv_ms, dt_d)
    if best_row is not None:
        return best_pack
    return None, best_err


def solve_transfer_direct(udp, idE, idL, n_phase=16, t0=0.0, raan=0.0,
                          argp=0.0):
    """Direct 2-impulse transfer (patched-conic seed → BCP correction).
    Synodic frame ⇒ Moon fixed at (1−μ,0,0); only t0 (Sun phase) matters.
    Returns (row21, mass, dv_ms, dt_d) for the best VALID transfer found,
    else (None, best_closest_approach_err_m)."""
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    D = L  # Earth–Moon distance (non-dim 1) in SI
    best_err = np.inf

    for ea in np.linspace(0.0, 2 * np.pi, n_phase, endpoint=False):
        r0, v0 = pk.par2ic([aE, eE, iE, raan, argp, ea], MU_EARTH)
        r0n = np.linalg.norm(r0)
        a_t = 0.5 * (r0n + D)
        v_peri = np.sqrt(MU_EARTH * (2.0 / r0n - 1.0 / a_t))
        vhat = np.array(v0) / np.linalg.norm(v0)
        dv0_inert = v_peri * vhat - np.array(v0)
        tof_seed = np.pi * np.sqrt(a_t**3 / MU_EARTH) / T  # non-dim

        pv0 = earth_orbit_state(aE, eE, iE, raan, argp, ea)
        dv0 = (dv0_inert / V).tolist()

        def closest(scale_tof, _pv0=pv0, _dv0=dv0, _ts=tof_seed):
            pv = propagate(_pv0, t0, [_dv0, [0, 0, 0], [0, 0, 0]],
                           [scale_tof * _ts, 0.0])
            if len(pv) == 0:
                return None
            return pv, abs(_r_moon(pv) - aM)

        # coarse TOF scan, then 1-D refine on the best
        cand = [(s, closest(s)) for s in np.linspace(0.6, 1.6, 11)]
        cand = [(s, c) for s, c in cand if c is not None]
        if not cand:
            continue
        s_b = min(cand, key=lambda z: z[1][1])[0]
        sol = least_squares(
            lambda s: (closest(s[0])[1] if closest(s[0]) else 1e9),
            [s_b], bounds=([0.5], [1.8]), xtol=1e-10, max_nfev=30,
        )
        c = closest(sol.x[0])
        if c is None:
            continue
        pv_a, err = c
        if err < best_err:
            best_err = err
        if err > aM * 1e-3:  # not near LOI band — try next phase
            continue
        dv2_res = solve_arrival_dv(pv_a, aM, eM, iM)
        if dv2_res is None:
            continue
        dv2, _ = dv2_res
        tof = sol.x[0] * tof_seed
        dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
        dt_d = tof * T * pk.SEC2DAY
        row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
               *dv0, 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
        f = udp.fitness(row)[0]
        if f < 0:  # valid (negated mass)
            return row, -f, dv_ms, dt_d, err
    return None, best_err


def solve_transfer_back(udp, idE, idL, n_seed=8, tof_grid=(3.0, 5.0, 8.0)):
    """Backward shooting (M-018 pivot). The LLO arrival is an EXACT
    initial condition; backward-propagate to the forgiving Earth side
    (384 m a-tol). Variables: LLO arrival ν, LOI ΔV (retro), TOF, Sun
    phase. Returns best valid (row21, mass, dv_ms, dt_d) or
    (None, best_earth_radius_err_m)."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best_pack, best_mass, best_err = None, -1.0, np.inf
    rng = np.random.default_rng(0)

    for tof_d in tof_grid:
        tof = tof_d * 86400.0 / T
        for _k in range(n_seed):
            nuM = rng.uniform(0, 2 * np.pi)
            OmM = rng.uniform(0, 2 * np.pi)
            # seed: retro LOI ~ a few hundred m/s (the burn we minimise)
            dv2_seed = np.array([0.0, 0.0, 0.0])
            arr = moon_orbit_state(aL, eL, iL, OmM, 0.0, nuM)
            # pre-LOI Moon-relative speed for a retro insertion guess
            _, vmf = _moon_inertial(arr)
            sp = np.linalg.norm(vmf)
            dv2_seed = (vmf / sp) * (300.0 / V) if sp > 0 else dv2_seed

            def resid(p, _OmM=OmM, _tof=tof):
                nu, t_arr = p[0], p[1]
                dv2 = p[2:5]
                a = moon_orbit_state(aL, eL, iL, _OmM, 0.0, nu)
                S = [a[0], [a[1][0] - dv2[0], a[1][1] - dv2[1],
                            a[1][2] - dv2[2]]]
                D = _back_state(S[0], S[1], t_arr, _tof)
                if D is None:
                    return [10.0]
                r_ef, _ = _earth_inertial([[D[0], D[1], D[2]],
                                           [D[3], D[4], D[5]]])
                return [(np.linalg.norm(r_ef) - aE) / L]

            x0 = np.array([nuM, 0.0, *dv2_seed])
            sol = least_squares(resid, x0, method="trf",
                                xtol=1e-10, max_nfev=80)
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
            best_err = min(best_err, abs(np.linalg.norm(r_ef) - aE))
            dep = solve_departure_dv(d_state, aE, eE, iE)
            if dep is None:
                continue
            posvel0, dv0, _ = dep
            row = [idE, idL, 0, t_arr - tof, *posvel0[0], *posvel0[1],
                   *dv0, 0.0, 0.0, 0.0, *dv2.tolist(), float(tof), 0.0]
            f = udp.fitness(row)[0]
            if f < 0 and -f > best_mass:
                dvms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
                best_mass = -f
                best_pack = (row, -f, dvms,
                             (t_arr - (t_arr - tof)) * T * pk.SEC2DAY)
    return best_pack if best_pack else (None, best_err)


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

    # (3) differential-corrected transfer attempt, Earth 0 → Moon 0
    import time as _t

    t0 = _t.time()
    res = solve_transfer_dc(udp, 0, 0, n_ea=4, t0_grid=(0.0,))
    dt = _t.time() - t0
    if res[0] is None:
        print(f"DC transfer E0→M0: NO valid transfer in {dt:.0f}s; "
              f"best |Δr_moon|={res[1]:.3e} m (LOI band ≈ {aM:.0f} m)")
    else:
        row, mass, dv_ms, dt_d = res
        print(f"DC transfer E0→M0 VALID in {dt:.0f}s: mass={mass:.1f} kg, "
              f"ΔV={dv_ms:.1f} m/s, ΔT={dt_d:.2f} d")

    # (4) backward-shooting attempt (M-018 pivot), Earth 0 → Moon 0
    t0 = _t.time()
    rb = solve_transfer_back(udp, 0, 0, n_seed=6, tof_grid=(3.0, 5.0, 8.0))
    dt = _t.time() - t0
    if rb[0] is None:
        print(f"BACK transfer E0->M0: NO valid in {dt:.0f}s; "
              f"best earth-radius err={rb[1]:.3e} m "
              f"(aE~{udp.earth_data[0][0]:.0f})")
    else:
        row, mass, dv_ms, dt_d = rb
        print(f"BACK transfer E0→M0 VALID in {dt:.0f}s: mass={mass:.1f} kg,"
              f" ΔV={dv_ms:.1f} m/s, ΔT={dt_d:.2f} d")
