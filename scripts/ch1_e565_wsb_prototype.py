"""E-565 — WSB / Sun-assisted ballistic-capture prototype, single pair.

Gate experiment for lever L4 (A-2026-05-29 coherent model): demonstrate
ONE pair end-to-end under the OFFICIAL fitness, or kill with evidence.

Pair: (idE=118, idL=171). Bank baseline 949 kg (dv=3777 m/s, dt=20.7d,
idD=108 with c_ld=30.9 -> no capacity masking up to dt~165d).

Architecture (3 impulses, official chromosome):
  dv0 at t0   : prograde burn on the Earth orbit, apogee -> 1.2-1.5e9 m
  coast T1    : out to apogee; solar tide raises perigee toward Moon
                distance and twists the plane (free plane change)
  dv1 at apo  : small midcourse (tens of m/s) targeting lunar perilune
                inside the target-orbit radius window
  coast T2    : fall back, encounter Moon at low v_inf
  dv2         : ballistic-capture insertion via solve_arrival_eccentric

Phases:
  A  ballistic grid scan over (ea_dep, t0 sun phase, r_apo): find
     configs whose free return already comes near the Moon
  B  midcourse DC on dv1 at apogee -> drive perilune into the window,
     then scan in-window samples with solve_arrival_eccentric, official
     fitness eval
  C  capacity-discount analysis over the whole bank

Run: PYTHONPATH=src micromamba run -n spoc26 python scripts/ch1_e565_wsb_prototype.py
Log: runs/ch1/77_e565_wsb_prototype.log  (tee from caller)
"""
from __future__ import annotations

import math
import sys
import time

import numpy as np
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON as MU,
    LtlTrajectory, earth_orbit_state,
)
from esa_spoc_26.ch1_trajectory_solve import _ta
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

BASE = "reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
IDE, IDL = 118, 171
IDD_BANK = 108          # idD used by the bank for this pair (c_ld=30.9)
BASELINE_MASS = 949.0   # bank m_l = m_d for this pair
BASELINE_DV = 3777.0
DAY = 86400.0 / T       # one day in nondim time
R_E_KO2 = ((6378137.0 + 99000.0) / L) ** 2   # Earth keep-out (squared, nd)
R_M_KO2 = ((1737400.0 + 30000.0) / L) ** 2   # Moon keep-out
SUN_PERIOD = 2 * np.pi / 0.925195985         # synodic month, nondim


def prograde_dv0(pv0, r_apo_m):
    """Prograde synodic-basis burn raising Earth-frame apogee to r_apo_m."""
    x, y, z = pv0[0]
    vx, vy, vz = pv0[1]
    v_ef = np.array([vx - y, vy + x + MU, vz])      # inertial vel, syn basis (nd)
    r0 = math.sqrt(((x + MU) * L) ** 2 + (y * L) ** 2 + (z * L) ** 2)
    v_req = math.sqrt(MU_EARTH * (2.0 / r0 - 2.0 / (r0 + r_apo_m)))
    s = v_req / (np.linalg.norm(v_ef) * V) - 1.0
    return v_ef * s


def sample_traj(pv0, t0, dv0, dv1=None, t1=None, t_max_d=135.0, dt_d=0.25):
    """Propagate BCP from pv0+dv0 at t0; optionally apply dv1 at t0+t1.
    Returns dict with sampled arrays and impact flag."""
    ta = _ta()
    ta.time = t0
    ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                   pv0[1][0] + dv0[0], pv0[1][1] + dv0[1], pv0[1][2] + dv0[2]]
    n = int(t_max_d / dt_d)
    ts, states = [], []
    impact = None
    kicked = dv1 is None
    for k in range(1, n + 1):
        t_target = t0 + k * dt_d * DAY
        if not kicked and t1 is not None and (k * dt_d * DAY) >= t1:
            # land exactly on t1, apply dv1, then continue
            try:
                ta.propagate_until(t0 + t1)
            except Exception:
                impact = "int"
                break
            ta.state[3] += dv1[0]
            ta.state[4] += dv1[1]
            ta.state[5] += dv1[2]
            kicked = True
        try:
            ta.propagate_until(t_target)
        except Exception:
            impact = "int"
            break
        s6 = ta.state
        re2 = (s6[0] + MU) ** 2 + s6[1] ** 2 + s6[2] ** 2
        rm2 = (s6[0] - 1 + MU) ** 2 + s6[1] ** 2 + s6[2] ** 2
        if re2 < R_E_KO2:
            impact = "earth"
            break
        if rm2 < R_M_KO2:
            impact = "moon"
            break
        ts.append(k * dt_d * DAY)            # time since t0, nondim
        states.append(np.array(s6[:6]))
    if not states:
        return None
    S = np.array(states)
    ts = np.array(ts)
    re = np.sqrt((S[:, 0] + MU) ** 2 + S[:, 1] ** 2 + S[:, 2] ** 2)
    rm = np.sqrt((S[:, 0] - 1 + MU) ** 2 + S[:, 1] ** 2 + S[:, 2] ** 2)
    return {"t": ts, "S": S, "re": re, "rm": rm, "impact": impact}


def moon_rel(s6):
    """Moon-relative r (m), v (m/s), and two-body energy (J/kg)."""
    r = np.array([(s6[0] - 1 + MU) * L, s6[1] * L, s6[2] * L])
    v = np.array([(s6[3] - s6[1]) * V, (s6[4] + s6[0]) * V - (1 - MU) * V,
                  s6[5] * V])
    rn = np.linalg.norm(r)
    vn = np.linalg.norm(v)
    return rn, vn, 0.5 * vn ** 2 - MU_MOON / rn


# ---------------------------------------------------------------- Phase A
def phase_a(udp, n_ea=16, n_t0=12, r_apos=(1.2e9, 1.35e9, 1.5e9),
            raans=(0.0,)):
    aE, eE, iE = udp.earth_data[IDE]
    print(f"\n=== Phase A: ballistic scan pair ({IDE},{IDL}) "
          f"{n_ea}x{n_t0}x{len(r_apos)}x{len(raans)} ===", flush=True)
    t_start = time.time()
    cands = []
    n_esc, n_imp = 0, 0
    for raan in raans:
        for ea in np.linspace(0, 2 * np.pi, n_ea, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, raan, 0.0, ea)
            for t0 in np.linspace(0, SUN_PERIOD, n_t0, endpoint=False):
                for r_apo in r_apos:
                    dv0 = prograde_dv0(pv0, r_apo)
                    tr = sample_traj(pv0, t0, dv0.tolist(), t_max_d=135.0)
                    if tr is None or tr["impact"] == "earth":
                        n_imp += 1
                        continue
                    re_max = tr["re"].max() * L
                    if re_max > 2.5e9:       # escaped Hill sphere
                        n_esc += 1
                        continue
                    # only consider lunar approach after the apogee pass
                    k_apo = int(np.argmax(tr["re"]))
                    if k_apo + 5 >= len(tr["t"]):
                        n_esc += 1
                        continue
                    rm_after = tr["rm"][k_apo:]
                    k_min = k_apo + int(np.argmin(rm_after))
                    rm_min = tr["rm"][k_min] * L
                    rn, vn, e2 = moon_rel(tr["S"][k_min])
                    cands.append(dict(raan=raan, ea=ea, t0=t0, r_apo=r_apo,
                                      dv0=dv0, rm_min=rm_min,
                                      t_apo_d=tr["t"][k_apo] / DAY,
                                      t_min_d=tr["t"][k_min] / DAY,
                                      v_rel=vn, e2=e2,
                                      perigee_post=re_max and tr["re"][k_apo:].min() * L,
                                      re_max=re_max))
    cands.sort(key=lambda c: c["rm_min"])
    print(f"scan done in {time.time()-t_start:.0f}s: {len(cands)} bound returns, "
          f"{n_esc} escapes, {n_imp} impacts/failures", flush=True)
    print(f"{'ea':>5} {'t0':>5} {'rapo9':>5} {'dv0':>5} {'tapo':>5} {'tmin':>5} "
          f"{'rm_min_km':>10} {'v_rel':>6} {'E2':>9} {'perig_km':>9}")
    for c in cands[:20]:
        print(f"{c['ea']:>5.2f} {c['t0']:>5.2f} {c['r_apo']/1e9:>5.2f} "
              f"{np.linalg.norm(c['dv0'])*V:>5.0f} {c['t_apo_d']:>5.1f} "
              f"{c['t_min_d']:>5.1f} {c['rm_min']/1e3:>10.0f} {c['v_rel']:>6.0f} "
              f"{c['e2']:>9.0f} {c['perigee_post']/1e3:>9.0f}", flush=True)
    return cands


# ---------------------------------------------------------------- Phase B
def perilune_after_kick(pv0, t0, dv0, dv1, t1, t_max_d):
    """Min Moon distance (nd) after midcourse kick; coarse then fine."""
    tr = sample_traj(pv0, t0, dv0, dv1=dv1, t1=t1, t_max_d=t_max_d, dt_d=0.25)
    if tr is None:
        return None, None, None
    if tr["impact"] == "earth":
        return None, None, None
    k1 = int(np.searchsorted(tr["t"], t1) + 2)
    if k1 >= len(tr["t"]) - 2:
        return None, None, None
    k_min = k1 + int(np.argmin(tr["rm"][k1:]))
    return tr["rm"][k_min], tr["t"][k_min], tr


def dc_midcourse(udp, cand, r_tgt_nd, t_max_d=160.0, verbose=True,
                 e2_tgt=None, e2_scale=5e4, seed=None):
    """Least-squares on dv1 (3 vars) at apogee. Residuals: perilune radius
    minus target, plus (optionally) Moon-relative two-body energy at
    perilune minus target. Returns (dv1, t1, perilune_nd, ...) or None."""
    aE, eE, iE = udp.earth_data[IDE]
    pv0 = earth_orbit_state(aE, eE, iE, cand["raan"], 0.0, cand["ea"])
    dv0 = cand["dv0"].tolist()
    t0 = cand["t0"]
    t1 = cand["t_apo_d"] * DAY

    def peri_state(p):
        tr = sample_traj(pv0, t0, dv0, dv1=p, t1=t1, t_max_d=t_max_d,
                         dt_d=0.25)
        if tr is None or tr["impact"] == "earth":
            return None
        k1 = int(np.searchsorted(tr["t"], t1) + 2)
        if k1 >= len(tr["t"]) - 2:
            return None
        k_min = k1 + int(np.argmin(tr["rm"][k1:]))
        return tr["rm"][k_min], tr["S"][k_min], tr["t"][k_min], tr

    def resid(p):
        out = peri_state(p.tolist())
        if out is None:
            return [10.0] * (2 if e2_tgt is not None else 1)
        rmin, s6, _, _ = out
        rr = (rmin - r_tgt_nd) / 1e-3
        if e2_tgt is None:
            return [rr]
        _, _, e2 = moon_rel(s6)
        return [rr, (e2 - e2_tgt) / e2_scale]

    try:
        sol = least_squares(resid, np.zeros(3) if seed is None else seed,
                            method="trf",
                            diff_step=2e-4, xtol=1e-12, ftol=1e-10,
                            max_nfev=80)
    except Exception as ex:
        if verbose:
            print(f"   DC exception: {ex}")
        return None
    out = peri_state(sol.x.tolist())
    if out is None:
        return None
    rmin, s6, t_peri, tr = out
    return sol.x, t1, rmin, t_peri, tr, pv0, s6


def arrival_search(udp, pv0, t0, dv0, dv1, t1, tr, aL, eL, iL):
    """Fine-sample the in-window arc near perilune; try arrival at each
    point; evaluate official fitness. Returns best (mass, row, info)."""
    r_lo, r_hi = aL * (1 - eL) / L, aL * (1 + eL) / L
    # locate coarse samples in/near window after t1
    k1 = int(np.searchsorted(tr["t"], t1) + 2)
    near = [k for k in range(k1, len(tr["t"])) if tr["rm"][k] < r_hi * 3.0]
    if not near:
        return None, "no_near_samples"
    t_a, t_b = tr["t"][near[0]] - 0.3 * DAY, tr["t"][min(near[-1] + 1,
                                                          len(tr["t"]) - 1)]
    # fine re-propagation over [t_a, t_b]
    ta = _ta()
    ta.time = t0
    ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                   pv0[1][0] + dv0[0], pv0[1][1] + dv0[1], pv0[1][2] + dv0[2]]
    try:
        ta.propagate_until(t0 + t1)
    except Exception:
        return None, "int_fail"
    ta.state[3] += dv1[0]
    ta.state[4] += dv1[1]
    ta.state[5] += dv1[2]
    n_fine = 1200
    dt_f = (t_b - t_a) / n_fine
    try:
        ta.propagate_until(t0 + t_a)
    except Exception:
        return None, "int_fail"
    best = None
    reject = {"window": 0, "arr_none": 0, "fit": 0}
    n_in = 0
    for k in range(n_fine):
        try:
            ta.propagate_until(t0 + t_a + (k + 1) * dt_f)
        except Exception:
            break
        s6 = np.array(ta.state[:6])
        rm = math.sqrt((s6[0] - 1 + MU) ** 2 + s6[1] ** 2 + s6[2] ** 2)
        if rm < math.sqrt(R_M_KO2):
            break
        if not (r_lo <= rm <= r_hi):
            reject["window"] += 1
            continue
        n_in += 1
        if n_in % 4 != 1:        # arrival solve every 4th in-window sample
            continue
        pv_arr = [s6[:3].tolist(), s6[3:].tolist()]
        res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
        if res is None:
            reject["arr_none"] += 1
            continue
        dv2 = res[0]
        T2 = (t_a + (k + 1) * dt_f) - t1
        dvtot = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
                 + np.linalg.norm(dv2)) * V
        row = [IDE, IDL, IDD_BANK, t0, *pv0[0], *pv0[1],
               *list(dv0), *list(dv1), *dv2.tolist(), t1, T2]
        pad = [-1.0] + [0.0] * 20
        chrom = list(row) + pad * (udp.dim // 21 - 1)
        f = udp.fitness(chrom)[0]
        if f >= 0:
            reject["fit"] += 1
            continue
        mass = -f
        if best is None or mass > best[0]:
            rn, vn, e2 = moon_rel(s6)
            best = (mass, row, dict(dv_tot=dvtot,
                                    dv0=np.linalg.norm(dv0) * V,
                                    dv1=np.linalg.norm(dv1) * V,
                                    dv2=np.linalg.norm(dv2) * V,
                                    dt_d=(t1 + T2) / DAY,
                                    r_arr=rn, v_rel=vn, e2=e2))
    return best, f"in_window={n_in} rejects={reject}"


def phase_b(udp, cands, n_try=10, mode="energy"):
    """mode='radius': DC perilune radius only (v1 behaviour).
    mode='energy': rank candidates by Moon-relative energy at closest
    approach and add an energy residual — drive toward ballistic capture
    (E2 target = 0.5*(300 m/s)^2) at the orbit's perilune."""
    aL, eL, iL = udp.moon_data[IDL]
    print(f"\n=== Phase B ({mode}): midcourse DC + capture, top {n_try} ===",
          flush=True)
    if mode == "energy":
        pool = [c for c in cands if c["rm_min"] < 3.5e8]
        pool.sort(key=lambda c: c["e2"])
        r_tgt = aL * (1 - eL) * 1.15 / L   # capture near perilune (Oberth)
        e2_tgt = 0.5 * 300.0 ** 2
    else:
        pool = cands
        r_tgt = aL * (1 - 0.5 * eL) / L
        e2_tgt = None
    best_overall = None
    for i, cand in enumerate(pool[:n_try]):
        t_st = time.time()
        out = dc_midcourse(udp, cand, r_tgt, e2_tgt=e2_tgt)
        if out is None:
            print(f" [{i}] DC failed (ea={cand['ea']:.2f} t0={cand['t0']:.2f} "
                  f"rapo={cand['r_apo']/1e9:.2f})", flush=True)
            continue
        dv1, t1, rmin, t_peri, tr, pv0, s6p = out
        dv1_ms = np.linalg.norm(dv1) * V
        _, v_rel_p, e2_p = moon_rel(s6p)
        print(f" [{i}] ea={cand['ea']:.2f} t0={cand['t0']:.2f} "
              f"rapo={cand['r_apo']/1e9:.2f}: dv1={dv1_ms:.1f} m/s -> "
              f"perilune {rmin*L/1e3:.0f} km at t={t_peri/DAY:.1f}d "
              f"v_rel={v_rel_p:.0f} E2={e2_p:.0f} ({time.time()-t_st:.0f}s)",
              flush=True)
        if rmin * L > aL * (1 + eL) * 1.5:
            continue
        best, diag = arrival_search(udp, pv0, cand["t0"], cand["dv0"].tolist(),
                                    dv1.tolist(), t1, tr, aL, eL, iL)
        print(f"     arrival: {diag}", flush=True)
        if best:
            m, row, info = best
            print(f"     *** VALID mass={m:.1f} kg  dv={info['dv_tot']:.0f} "
                  f"(dv0={info['dv0']:.0f} dv1={info['dv1']:.0f} "
                  f"dv2={info['dv2']:.0f})  dt={info['dt_d']:.1f}d "
                  f"r_arr={info['r_arr']/1e3:.0f}km v_rel={info['v_rel']:.0f} "
                  f"E2={info['e2']:.0f} ***", flush=True)
            if best_overall is None or m > best_overall[0]:
                best_overall = best
    return best_overall


# ------------------------------------------------------------- Phase B v3
def _peri_info(pv0, t0, dv0, dv1, t1, t_max_d=160.0):
    """Perilune state after kick: (r_nd, s6, t_peri, tr) or None."""
    tr = sample_traj(pv0, t0, dv0, dv1=dv1, t1=t1, t_max_d=t_max_d, dt_d=0.25)
    if tr is None or tr["impact"] == "earth":
        return None
    k1 = int(np.searchsorted(tr["t"], t1) + 2)
    if k1 >= len(tr["t"]) - 2:
        return None
    k_min = k1 + int(np.argmin(tr["rm"][k1:]))
    return tr["rm"][k_min], tr["S"][k_min], tr["t"][k_min], tr


def capture_proxy(s6, rm_nd, aL, eL, iL):
    """Alignment-aware lower-bound estimate of dv2 [m/s] at perilune."""
    r = np.array([(s6[0] - 1 + MU) * L, s6[1] * L, s6[2] * L])
    v = np.array([(s6[3] - s6[1]) * V, (s6[4] + s6[0]) * V - (1 - MU) * V,
                  s6[5] * V])
    rn, vn = np.linalg.norm(r), np.linalg.norm(v)
    e2 = 0.5 * vn ** 2 - MU_MOON / rn
    r_lo, r_hi = aL * (1 - eL), aL * (1 + eL)
    r_eff = min(max(rn, r_lo), r_hi)
    val = 2 * (e2 + MU_MOON / r_eff)
    if val <= 0:
        return 1e9
    v_at = math.sqrt(val)
    v_orb = math.sqrt(MU_MOON * (2.0 / r_eff - 1.0 / aL))
    h = np.cross(r, v)
    hn = np.linalg.norm(h)
    if hn < 1e-9:
        return 1e9
    i_traj = math.acos(max(-1.0, min(1.0, h[2] / hn)))
    di = abs(i_traj - iL)
    return math.sqrt((v_at - v_orb) ** 2 + (min(v_at, v_orb) * di) ** 2)


def phase_b3(udp, cands, n_seed=12, t_max_d=160.0):
    """Grid over dv1 at apogee scored by alignment-aware capture proxy,
    then Nelder-Mead on the EXACT objective (solve_arrival_eccentric in
    the loop), then official-fitness arrival search."""
    from scipy.optimize import minimize
    aL, eL, iL = udp.moon_data[IDL]
    aE, eE, iE = udp.earth_data[IDE]
    print(f"\n=== Phase B3: proxy-grid + exact-objective NM, "
          f"{n_seed} seeds ===", flush=True)
    pool = [c for c in cands if c["rm_min"] < 3.5e8]
    pool.sort(key=lambda c: c["e2"])
    seen, seeds = set(), []
    for c in pool + sorted(cands, key=lambda c: c["rm_min"]):
        key = (round(c["ea"], 3), round(c["t0"], 3), c["r_apo"])
        if key not in seen:
            seen.add(key)
            seeds.append(c)
    best_overall = None
    for i, cand in enumerate(seeds[:n_seed]):
        t_st = time.time()
        pv0 = earth_orbit_state(aE, eE, iE, cand["raan"], 0.0, cand["ea"])
        dv0 = cand["dv0"].tolist()
        t0, t1 = cand["t0"], cand["t_apo_d"] * DAY
        # apogee state for local frame
        ta = _ta()
        ta.time = t0
        ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                       pv0[1][0] + dv0[0], pv0[1][1] + dv0[1],
                       pv0[1][2] + dv0[2]]
        try:
            ta.propagate_until(t0 + t1)
        except Exception:
            continue
        s_apo = np.array(ta.state[:6])
        v_in = np.array([s_apo[3] - s_apo[1], s_apo[4] + s_apo[0] + MU,
                         s_apo[5]])
        v_hat = v_in / np.linalg.norm(v_in)
        r_e = np.array([s_apo[0] + MU, s_apo[1], s_apo[2]])
        r_hat = r_e / np.linalg.norm(r_e)
        n_hat = np.cross(v_hat, r_hat)
        n_hat /= np.linalg.norm(n_hat)
        # proxy grid
        best_g = None
        for a_ms in np.linspace(-150, 150, 7):
            for b_ms in np.linspace(-150, 150, 7):
                for c_ms in (-60.0, 0.0, 60.0):
                    dv1 = (a_ms * v_hat + b_ms * n_hat + c_ms * r_hat) / V
                    out = _peri_info(pv0, t0, dv0, dv1.tolist(), t1, t_max_d)
                    if out is None:
                        continue
                    rm_nd, s6, t_p, _ = out
                    if rm_nd * L > aL * (1 + eL) * 4:
                        continue
                    dv2p = capture_proxy(s6, rm_nd, aL, eL, iL)
                    # radius penalty if perilune above window
                    pen = max(0.0, (rm_nd * L - aL * (1 + eL)) / 1e5)
                    score = (np.linalg.norm(dv1) * V + dv2p + pen)
                    if best_g is None or score < best_g[0]:
                        best_g = (score, dv1, rm_nd, s6, t_p)
        if best_g is None:
            print(f" [{i}] no grid point survives", flush=True)
            continue
        score, dv1_g, rm_g, s6_g, tp_g = best_g
        _, vrel_g, e2_g = moon_rel(s6_g)
        print(f" [{i}] ea={cand['ea']:.2f} t0={cand['t0']:.2f} "
              f"rapo={cand['r_apo']/1e9:.2f}: grid best |dv1|="
              f"{np.linalg.norm(dv1_g)*V:.0f} m/s peri={rm_g*L/1e3:.0f}km "
              f"v_rel={vrel_g:.0f} E2={e2_g:.0f} proxy_extra={score:.0f} "
              f"({time.time()-t_st:.0f}s)", flush=True)

        # exact-objective NM polish
        def f_exact(p):
            out = _peri_info(pv0, t0, dv0, p.tolist(), t1, t_max_d)
            if out is None:
                return 1e9
            rm_nd, s6, t_p, tr = out
            if rm_nd * L > aL * (1 + eL):
                return 8000.0 + (rm_nd * L - aL * (1 + eL)) / 1e5
            # sample a few in-window points around perilune (coarse arc)
            k1 = int(np.searchsorted(tr["t"], t1) + 2)
            ks = [k for k in range(k1, len(tr["t"]))
                  if aL * (1 - eL) / L <= tr["rm"][k] <= aL * (1 + eL) / L]
            best_dv2 = None
            for k in ks[::2][:8]:
                res = solve_arrival_eccentric(
                    [tr["S"][k][:3].tolist(), tr["S"][k][3:].tolist()],
                    aL, eL, iL)
                if res is None:
                    continue
                n2 = np.linalg.norm(res[0]) * V
                if best_dv2 is None or n2 < best_dv2:
                    best_dv2 = n2
            if best_dv2 is None:
                return 7000.0
            return (np.linalg.norm(dv0) + np.linalg.norm(p)) * V + best_dv2

        t_nm = time.time()
        sol = minimize(f_exact, dv1_g, method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 0.5,
                                "maxfev": 220, "disp": False,
                                "initial_simplex": np.array(
                                    [dv1_g] + [dv1_g + 8.0 / V * e
                                               for e in (v_hat, n_hat, r_hat)])})
        dv_tot_exact = sol.fun
        print(f"     NM: dv_total={dv_tot_exact:.0f} m/s "
              f"(|dv1|={np.linalg.norm(sol.x)*V:.0f}) "
              f"[{time.time()-t_nm:.0f}s, {sol.nfev} evals]", flush=True)
        if dv_tot_exact > 6000:
            continue
        out = _peri_info(pv0, t0, dv0, sol.x.tolist(), t1, t_max_d)
        if out is None:
            continue
        _, _, _, tr = out
        best, diag = arrival_search(udp, pv0, t0, dv0, sol.x.tolist(),
                                    t1, tr, aL, eL, iL)
        print(f"     arrival: {diag}", flush=True)
        if best:
            m, row, info = best
            print(f"     *** VALID mass={m:.1f} kg dv={info['dv_tot']:.0f} "
                  f"(dv0={info['dv0']:.0f} dv1={info['dv1']:.0f} "
                  f"dv2={info['dv2']:.0f}) dt={info['dt_d']:.1f}d "
                  f"r_arr={info['r_arr']/1e3:.0f}km "
                  f"v_rel={info['v_rel']:.0f} E2={info['e2']:.0f} ***",
                  flush=True)
            if best_overall is None or m > best_overall[0]:
                best_overall = best
    return best_overall


def main():
    import pickle, os
    udp = LtlTrajectory(BASE)
    aE, eE, iE = udp.earth_data[IDE]
    aL, eL, iL = udp.moon_data[IDL]
    print(f"pair ({IDE},{IDL}): aE={aE:.3e} eE={eE:.3f} iE={iE:.3f} | "
          f"aL={aL:.3e} eL={eL:.3f} iL={iL:.3f}")
    print(f"baseline (bank): {BASELINE_MASS} kg, dv={BASELINE_DV} m/s")
    cache = "runs/ch1/e565_phase_a.pkl"
    if os.path.exists(cache) and "--rescan" not in sys.argv:
        cands = pickle.load(open(cache, "rb"))
        print(f"(phase A loaded from cache: {len(cands)} candidates)")
    else:
        cands = phase_a(udp)
        pickle.dump(cands, open(cache, "wb"))
    if not cands:
        print("Phase A: no bound returns — verdict input: WSB outbound "
              "geometry not survivable in this BCP")
        return
    n_try = 10
    for a in sys.argv:
        if a.startswith("--n="):
            n_try = int(a[4:])
    if "--radius" in sys.argv:
        best = phase_b(udp, cands, n_try=n_try, mode="radius")
    elif "--energy" in sys.argv:
        best = phase_b(udp, cands, n_try=n_try, mode="energy")
    else:
        best = phase_b3(udp, cands, n_seed=n_try)
    if best:
        m, row, info = best
        print(f"\n=== E-565 RESULT: WSB mass {m:.1f} kg vs baseline "
              f"{BASELINE_MASS} kg ({m-BASELINE_MASS:+.1f}) ===")
        print("row:", [round(v, 12) if isinstance(v, float) else v
                       for v in row])
    else:
        print("\n=== E-565 RESULT: no valid WSB capture found ===")


if __name__ == "__main__":
    main()
