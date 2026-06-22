"""E-701: STM-based differential corrector for the backward-shooting Ch1-trajectory solver.

Finite-diff DCs stall at ~1 km on sensitive 3-body arcs because the finite-diff Jacobian of the
PROPAGATION (d D / d initial_state) is noise-dominated. heyoka's variational equations give that 6x6
block ANALYTICALLY (the STM, machine-precision). We assemble a mixed Jacobian: STM for the sensitive
propagation block, finite-diff for the well-conditioned algebraic maps (state2earth, dD/dtof). A
damped minimum-norm Newton step then closes the Earth-side orbit match to the official 384m/1e-6.

Public API:
  back_state_stm(arr_pos, v_pre, t_arr, tof) -> (D[6], STM[6,6])      # backward var-propagation
  stm_newton_back(x, aM,eM,iM, aE,eE,iE, ...) -> (x_corrected, info)  # corrector on the UDPBack vector
"""
import sys, math
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import (
    moon_orbit_state, state2earth, L,
    CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S, bcp_dyn,
)

_PARS = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
_TAV = None  # cached variational integrator (state + 6x6 STM)


def _tav():
    global _TAV
    if _TAV is None:
        import heyoka as hy
        vsys = hy.var_ode_sys(bcp_dyn(), hy.var_args.vars, order=1)
        _TAV = hy.taylor_adaptive(vsys, [0.0] * 6, tol=1e-16, compact_mode=True)
        _TAV.pars[:] = _PARS
    return _TAV


def back_state_stm(arr_pos, v_pre, t_arr, tof):
    """Backward-propagate the BCP from (arr_pos, v_pre) at t_arr to t_arr-tof, WITH the STM.
    Returns (D[6], STM[6,6]) where STM[i,j] = d D_i / d initial_state_j. None on failure."""
    ta = _tav()
    ta.time = t_arr
    ta.state[:6] = [arr_pos[0], arr_pos[1], arr_pos[2], v_pre[0], v_pre[1], v_pre[2]]
    ta.state[6:] = np.eye(6).flatten()      # variational ICs = identity
    try:
        ta.propagate_until(t_arr - tof)
    except Exception:
        return None
    D = np.array(ta.state[:6])
    STM = np.array(ta.state[6:42]).reshape(6, 6)
    return D, STM


def _pre_from_x(x, aM, eM, iM):
    """Arrival point on the Moon orbit and the pre-insertion velocity (S_vel - dv2)."""
    raan_m, argp_m, ea_m = x[0], x[1], x[2]
    dv2 = x[3:6]
    S = moon_orbit_state(aM, eM, iM, raan_m, argp_m, ea_m)
    arr_pos = np.array(S[0])
    v_pre = np.array(S[1]) - np.asarray(dv2)
    return arr_pos, v_pre


def _resid(D, aE, eE, iE):
    """Scaled Earth-side orbit-match residual; all three target |.|<1e-6 to pass the official window."""
    el = state2earth([[D[0], D[1], D[2]], [D[3], D[4], D[5]]])
    return np.array([(el[0] - aE) / L, el[1] - eE, el[2] - iE])


def _dg_dD(D, aE, eE, iE, h=1e-7):
    """3x6 finite-diff Jacobian of the (scaled) elements residual w.r.t. the 6-state D.
    Algebraic + well-conditioned, so finite-diff is clean here (unlike the propagation)."""
    r0 = _resid(D, aE, eE, iE)
    J = np.zeros((3, 6))
    for k in range(6):
        Dp = D.copy(); Dp[k] += h
        J[:, k] = (_resid(Dp, aE, eE, iE) - r0) / h
    return J


def stm_newton_back(x, aM, eM, iM, aE, eE, iE, iters=30, tol=1e-6, verbose=False):
    """Damped minimum-norm Newton corrector. Active DOF = dv2(3) + tof (cols 3,4,5,7 of x);
    arrival is exact by construction, so these four cleanly drive the Earth-side (a,e,i)."""
    x = np.array(x, dtype=float)
    active = [3, 4, 5, 7]                       # dv2x, dv2y, dv2z, tof
    best_x, best_norm = x.copy(), np.inf
    for it in range(iters):
        t_arr, tof = x[6], x[7]
        arr_pos, v_pre = _pre_from_x(x, aM, eM, iM)
        out = back_state_stm(arr_pos, v_pre, t_arr, tof)
        if out is None:
            break
        D, STM = out
        r = _resid(D, aE, eE, iE)
        rn = np.linalg.norm(r)
        if rn < best_norm:
            best_norm, best_x = rn, x.copy()
        if verbose:
            print(f"    it{it}: |r|={rn:.3e}  (a_miss={abs(r[0])*L:.1f}m e={abs(r[1]):.2e} i={abs(r[2]):.2e})", flush=True)
        if np.abs(r[0]) < tol and np.abs(r[1]) < tol and np.abs(r[2]) < tol:
            return x, {"ok": True, "iters": it, "rnorm": rn, "a_miss_m": abs(r[0]) * L}
        dgdD = _dg_dD(D, aE, eE, iE)
        # assemble dr/d(active): dv2 via STM (pre-velocity perturbation), tof via finite-diff endpoint
        J = np.zeros((3, 4))
        for col, k in enumerate([0, 1, 2]):     # dv2 components -> pre velocity perturbed by -1
            dpre = np.zeros(6); dpre[3 + k] = -1.0
            dD = STM @ dpre
            J[:, col] = dgdD @ dD
        htof = 1e-4
        out2 = back_state_stm(arr_pos, v_pre, t_arr, tof + htof)
        if out2 is None:
            break
        J[:, 3] = dgdD @ ((out2[0] - D) / htof)
        # damped minimum-norm step  step = -J^T (J J^T + lam I)^-1 r ; backtrack on |r|
        lam = 1e-12
        JJt = J @ J.T + lam * np.eye(3)
        try:
            step_full = -J.T @ np.linalg.solve(JJt, r)
        except np.linalg.LinAlgError:
            break
        alpha = 1.0
        improved = False
        for _ in range(12):
            xt = x.copy()
            for col, idx in enumerate(active):
                xt[idx] += alpha * step_full[col]
            xt[7] = max(xt[7], 0.3)             # keep tof positive/sane
            at, tf = xt[6], xt[7]
            ap, vp = _pre_from_x(xt, aM, eM, iM)
            o = back_state_stm(ap, vp, at, tf)
            if o is not None and np.linalg.norm(_resid(o[0], aE, eE, iE)) < rn:
                x = xt; improved = True; break
            alpha *= 0.5
        if not improved:
            break
    # final residual at best_x
    t_arr, tof = best_x[6], best_x[7]
    ap, vp = _pre_from_x(best_x, aM, eM, iM)
    o = back_state_stm(ap, vp, t_arr, tof)
    rn = np.linalg.norm(_resid(o[0], aE, eE, iE)) if o is not None else np.inf
    r = _resid(o[0], aE, eE, iE) if o is not None else np.array([9, 9, 9])
    return best_x, {"ok": bool(abs(r[0]) < tol and abs(r[1]) < tol and abs(r[2]) < tol),
                    "iters": iters, "rnorm": rn, "a_miss_m": abs(r[0]) * L}
