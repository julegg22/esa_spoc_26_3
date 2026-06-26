"""E-725 — Ch2-large rank-1: numba-vectorized transfer evaluator (matches KTTSP.compute_transfer).

The fine-epoch evaluator (E-723) calls pykep Lambert ~190k times per edge (~100s) -> the order-search
bottleneck. This reimplements eph (Kepler) + Izzo multi-rev Lambert in numba so a whole (epoch x tof) grid of
transfers evaluates in ~1s. Min-dv is taken over revs 0..max_revs and both directions, exactly like
compute_transfer. Validated against pykep to ~1e-6 before use.
"""
import numpy as np
from numba import njit

MU_MOON = 4.904869500000000e12
DAY2SEC = 86400.0


@njit(cache=True)
def kep_eph(row, t_rel_sec):
    """position+velocity (inertial) of a keplerian orbit `row`=[a,e,i,RAAN,argp,M0] at t_rel_sec after t0."""
    a, e, inc, W, w, M0 = row
    n = np.sqrt(MU_MOON / (a * a * a))
    M = M0 + n * t_rel_sec
    E = M
    for _ in range(60):
        E = E - (E - e * np.sin(E) - M) / (1.0 - e * np.cos(E))
    nu = 2.0 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))
    r = a * (1 - e * np.cos(E)); p = a * (1 - e * e); h = np.sqrt(MU_MOON * p)
    rpx = r * np.cos(nu); rpy = r * np.sin(nu)
    vpx = -MU_MOON / h * np.sin(nu); vpy = MU_MOON / h * (e + np.cos(nu))
    cO = np.cos(W); sO = np.sin(W); ci = np.cos(inc); si = np.sin(inc); cw = np.cos(w); sw = np.sin(w)
    r11 = cO * cw - sO * sw * ci; r12 = -cO * sw - sO * cw * ci
    r21 = sO * cw + cO * sw * ci; r22 = -sO * sw + cO * cw * ci
    r31 = sw * si; r32 = cw * si
    rx = r11 * rpx + r12 * rpy; ry = r21 * rpx + r22 * rpy; rz = r31 * rpx + r32 * rpy
    vx = r11 * vpx + r12 * vpy; vy = r21 * vpx + r22 * vpy; vz = r31 * vpx + r32 * vpy
    return rx, ry, rz, vx, vy, vz


# ---- Izzo 2015 multi-rev Lambert (faithful port of poliastro's njit implementation) ----
@njit(cache=True)
def _hyp2f1b(x):
    if x >= 1.0:
        return np.inf
    res = 1.0; term = 1.0; ii = 0.0
    while True:
        term = term * (3.0 + ii) * (1.0 + ii) / (2.5 + ii) * x / (ii + 1.0)
        res_old = res; res = res + term
        if res == res_old:
            return res
        ii += 1.0


@njit(cache=True)
def _compute_y(x, ll):
    return np.sqrt(1.0 - ll * ll * (1.0 - x * x))


@njit(cache=True)
def _compute_psi(x, y, ll):
    if -1.0 <= x < 1.0:
        return np.arccos(x * y + ll * (1.0 - x * x))
    elif x > 1.0:
        return np.arcsinh((y - x * ll) * np.sqrt(x * x - 1.0))
    return 0.0


@njit(cache=True)
def _tof_eq_y(x, y, T0, ll, M):
    if M == 0 and np.sqrt(0.6) < x < np.sqrt(1.4):
        eta = y - ll * x
        S_1 = 0.5 * (1.0 - ll - x * eta)
        Q = 4.0 / 3.0 * _hyp2f1b(S_1)
        return 0.5 * (eta * eta * eta * Q + 4.0 * ll * eta) - T0
    psi = _compute_psi(x, y, ll)
    return (((psi + M * np.pi) / np.sqrt(abs(1.0 - x * x))) - x + ll * y) / (1.0 - x * x) - T0


@njit(cache=True)
def _tof_eq_p(x, y, T, ll):
    return (3.0 * T * x - 2.0 + 2.0 * ll * ll * ll * x / y) / (1.0 - x * x)


@njit(cache=True)
def _tof_eq_p2(x, y, T, dT, ll):
    return (3.0 * T + 5.0 * x * dT + 2.0 * (1.0 - ll * ll) * ll * ll * ll / (y * y * y)) / (1.0 - x * x)


@njit(cache=True)
def _tof_eq_p3(x, y, T, dT, ddT, ll):
    return (7.0 * x * ddT + 8.0 * dT - 6.0 * (1.0 - ll * ll) * ll ** 5 * x / (y ** 5)) / (1.0 - x * x)


@njit(cache=True)
def _householder(p0, T0, ll, M):
    for _ in range(35):
        y = _compute_y(p0, ll)
        fval = _tof_eq_y(p0, y, T0, ll, M)
        T = fval + T0
        fder = _tof_eq_p(p0, y, T, ll)
        fder2 = _tof_eq_p2(p0, y, T, fder, ll)
        fder3 = _tof_eq_p3(p0, y, T, fder, fder2, ll)
        denom = fder * (fder * fder - fval * fder2) + fder3 * fval * fval / 6.0
        if denom == 0.0:
            return p0
        p = p0 - fval * ((fder * fder - fval * fder2 / 2.0) / denom)
        if abs(p - p0) < 1e-7:
            return p
        p0 = p
    return p0


@njit(cache=True)
def _initial_guess(T, ll, M, lowpath):
    if M == 0:
        T0 = np.arccos(ll) + ll * np.sqrt(1.0 - ll * ll)
        T1 = 2.0 / 3.0 * (1.0 - ll * ll * ll)
        if T >= T0:
            return (T0 / T) ** (2.0 / 3.0) - 1.0
        elif T < T1:
            return 5.0 / 2.0 * T1 / T * (T1 - T) / (1.0 - ll ** 5) + 1.0
        else:
            return (T0 / T) ** (np.log(T1 / T0) / np.log(2.0)) - 1.0
    else:
        x0l = (((M * np.pi + np.pi) / (8.0 * T)) ** (2.0 / 3.0) - 1.0) / \
              (((M * np.pi + np.pi) / (8.0 * T)) ** (2.0 / 3.0) + 1.0)
        x0r = (((8.0 * T) / (M * np.pi)) ** (2.0 / 3.0) - 1.0) / \
              (((8.0 * T) / (M * np.pi)) ** (2.0 / 3.0) + 1.0)
        if lowpath:
            return max(x0l, x0r)
        return min(x0l, x0r)


@njit(cache=True)
def lambert_dv(r1x, r1y, r1z, v1x, v1y, v1z, r2x, r2y, r2z, v2x, v2y, v2z, tof_sec, max_revs):
    """min over revs(0..max_revs), both multi-rev branches, and both transfer directions, of
    |v1L-v1|+|v2L-v2| (matches KTTSP.compute_transfer's min over cw and max_revs)."""
    r1 = np.sqrt(r1x * r1x + r1y * r1y + r1z * r1z)
    r2 = np.sqrt(r2x * r2x + r2y * r2y + r2z * r2z)
    cx = r2x - r1x; cy = r2y - r1y; cz = r2z - r1z
    c = np.sqrt(cx * cx + cy * cy + cz * cz)
    s = 0.5 * (r1 + r2 + c)
    lam = np.sqrt(1.0 - c / s)
    hx = r1y * r2z - r1z * r2y; hy = r1z * r2x - r1x * r2z; hz = r1x * r2y - r1y * r2x
    T = np.sqrt(2.0 * MU_MOON / (s * s * s)) * tof_sec
    gamma = np.sqrt(MU_MOON * s / 2.0)
    rho = (r1 - r2) / c
    sigma = np.sqrt(1.0 - rho * rho)
    ur1x = r1x / r1; ur1y = r1y / r1; ur1z = r1z / r1
    ur2x = r2x / r2; ur2y = r2y / r2; ur2z = r2z / r2
    Mmax = int(T / np.pi)
    if Mmax > max_revs:
        Mmax = max_revs
    best = 1e18
    for sign in range(2):
        ll = lam if sign == 0 else -lam
        ihx = hx; ihy = hy; ihz = hz
        if sign == 1:
            ihx = -hx; ihy = -hy; ihz = -hz
        hn = np.sqrt(ihx * ihx + ihy * ihy + ihz * ihz)
        if hn == 0.0:
            continue
        ihx /= hn; ihy /= hn; ihz /= hn
        it1x = ihy * ur1z - ihz * ur1y; it1y = ihz * ur1x - ihx * ur1z; it1z = ihx * ur1y - ihy * ur1x
        it2x = ihy * ur2z - ihz * ur2y; it2y = ihz * ur2x - ihx * ur2z; it2z = ihx * ur2y - ihy * ur2x
        for M in range(Mmax + 1):
            for lp in range(2 if M > 0 else 1):
                x0 = _initial_guess(T, ll, M, lp == 0)
                x = _householder(x0, T, ll, M)
                if x <= -1.0 or np.isnan(x):
                    continue
                y = _compute_y(x, ll)
                Vr1 = gamma * ((ll * y - x) - rho * (ll * y + x)) / r1
                Vr2 = -gamma * ((ll * y - x) + rho * (ll * y + x)) / r2
                Vt1 = gamma * sigma * (y + ll * x) / r1
                Vt2 = gamma * sigma * (y + ll * x) / r2
                V1x = Vr1 * ur1x + Vt1 * it1x; V1y = Vr1 * ur1y + Vt1 * it1y; V1z = Vr1 * ur1z + Vt1 * it1z
                V2x = Vr2 * ur2x + Vt2 * it2x; V2y = Vr2 * ur2y + Vt2 * it2y; V2z = Vr2 * ur2z + Vt2 * it2z
                dv = (np.sqrt((V1x - v1x) ** 2 + (V1y - v1y) ** 2 + (V1z - v1z) ** 2)
                      + np.sqrt((V2x - v2x) ** 2 + (V2y - v2y) ** 2 + (V2z - v2z) ** 2))
                if dv < best:
                    best = dv
    return best


@njit(cache=True)
def transfer_dv(rowi, rowj, t_dep_sec, tof_sec, max_revs):
    r1x, r1y, r1z, v1x, v1y, v1z = kep_eph(rowi, t_dep_sec)
    r2x, r2y, r2z, v2x, v2y, v2z = kep_eph(rowj, t_dep_sec + tof_sec)
    return lambert_dv(r1x, r1y, r1z, v1x, v1y, v1z, r2x, r2y, r2z, v2x, v2y, v2z, tof_sec, max_revs)
