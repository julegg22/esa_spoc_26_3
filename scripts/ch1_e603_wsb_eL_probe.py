"""E-603 — WSB / ballistic-capture probe STRATIFIED BY Moon eccentricity (eL).

Decisive diagnostic (Phase-4 experiment 1 of E-602): does Sun-assisted
ballistic capture (WSB) close the impulsive gap on LOW-eL (circular/LMO)
Moon targets — the high-value class corr(dv,eL)=-0.71 says is expensive
impulsively but where the capture window is narrowest — or does it only
help the HIGH-eL targets that were already cheap?

This REUSES the proven E-565 (E-036) pipeline (Phase A ballistic scan +
Phase B3 proxy-grid + exact-NM + official-fitness arrival search),
generalized to arbitrary (idE,idL,idD). PROBE ONLY: writes /tmp + scripts/,
never touches the bank, never submits.

Run:
  PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
      python scripts/ch1_e603_wsb_eL_probe.py
"""
from __future__ import annotations

import json
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch1_trajectory import (
    L, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON as MU,
    LtlTrajectory, earth_orbit_state,
)
from esa_spoc_26.ch1_trajectory_solve import _ta
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric
import pykep as pk

BASE = "reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
from esa_spoc_26.ch1_trajectory import T as T_NONDIM
DAY = 86400.0 / T_NONDIM
R_E_KO2 = ((6378137.0 + 99000.0) / L) ** 2
R_M_KO2 = ((1737400.0 + 30000.0) / L) ** 2
SUN_PERIOD = 2 * np.pi / 0.925195985
HOHMANN_FLOOR = 3940.0


# ----------------------------------------------------------- core mechanics
def prograde_dv0(pv0, r_apo_m):
    x, y, z = pv0[0]
    vx, vy, vz = pv0[1]
    v_ef = np.array([vx - y, vy + x + MU, vz])
    r0 = math.sqrt(((x + MU) * L) ** 2 + (y * L) ** 2 + (z * L) ** 2)
    v_req = math.sqrt(MU_EARTH * (2.0 / r0 - 2.0 / (r0 + r_apo_m)))
    s = v_req / (np.linalg.norm(v_ef) * V) - 1.0
    return v_ef * s


def sample_traj(pv0, t0, dv0, dv1=None, t1=None, t_max_d=135.0, dt_d=0.25):
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
        ts.append(k * dt_d * DAY)
        states.append(np.array(s6[:6]))
    if not states:
        return None
    S = np.array(states)
    ts = np.array(ts)
    re = np.sqrt((S[:, 0] + MU) ** 2 + S[:, 1] ** 2 + S[:, 2] ** 2)
    rm = np.sqrt((S[:, 0] - 1 + MU) ** 2 + S[:, 1] ** 2 + S[:, 2] ** 2)
    return {"t": ts, "S": S, "re": re, "rm": rm, "impact": impact}


def moon_rel(s6):
    r = np.array([(s6[0] - 1 + MU) * L, s6[1] * L, s6[2] * L])
    v = np.array([(s6[3] - s6[1]) * V, (s6[4] + s6[0]) * V - (1 - MU) * V,
                  s6[5] * V])
    rn = np.linalg.norm(r)
    vn = np.linalg.norm(v)
    return rn, vn, 0.5 * vn ** 2 - MU_MOON / rn


def capture_proxy(s6, rm_nd, aL, eL, iL):
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


def _peri_info(pv0, t0, dv0, dv1, t1, t_max_d=160.0):
    tr = sample_traj(pv0, t0, dv0, dv1=dv1, t1=t1, t_max_d=t_max_d, dt_d=0.25)
    if tr is None or tr["impact"] == "earth":
        return None
    k1 = int(np.searchsorted(tr["t"], t1) + 2)
    if k1 >= len(tr["t"]) - 2:
        return None
    k_min = k1 + int(np.argmin(tr["rm"][k1:]))
    return tr["rm"][k_min], tr["S"][k_min], tr["t"][k_min], tr


# ------------------------------------------------------------- Phase A
def phase_a(udp, idE, idL, n_ea=16, n_t0=12, r_apos=(1.2e9, 1.35e9, 1.5e9)):
    aE, eE, iE = udp.earth_data[idE]
    cands = []
    for ea in np.linspace(0, 2 * np.pi, n_ea, endpoint=False):
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea)
        for t0 in np.linspace(0, SUN_PERIOD, n_t0, endpoint=False):
            for r_apo in r_apos:
                dv0 = prograde_dv0(pv0, r_apo)
                tr = sample_traj(pv0, t0, dv0.tolist(), t_max_d=135.0)
                if tr is None or tr["impact"] == "earth":
                    continue
                re_max = tr["re"].max() * L
                if re_max > 2.5e9:
                    continue
                k_apo = int(np.argmax(tr["re"]))
                if k_apo + 5 >= len(tr["t"]):
                    continue
                rm_after = tr["rm"][k_apo:]
                k_min = k_apo + int(np.argmin(rm_after))
                rm_min = tr["rm"][k_min] * L
                rn, vn, e2 = moon_rel(tr["S"][k_min])
                cands.append(dict(ea=ea, t0=t0, r_apo=r_apo, dv0=dv0,
                                  rm_min=rm_min, t_apo_d=tr["t"][k_apo] / DAY,
                                  t_min_d=tr["t"][k_min] / DAY, v_rel=vn, e2=e2))
    cands.sort(key=lambda c: c["rm_min"])
    return cands


# ------------------------------------------------------------- arrival search
def arrival_search(udp, idE, idL, idD, pv0, t0, dv0, dv1, t1, tr, aL, eL, iL):
    r_lo, r_hi = aL * (1 - eL) / L, aL * (1 + eL) / L
    k1 = int(np.searchsorted(tr["t"], t1) + 2)
    near = [k for k in range(k1, len(tr["t"])) if tr["rm"][k] < r_hi * 3.0]
    if not near:
        return None
    t_a = tr["t"][near[0]] - 0.3 * DAY
    t_b = tr["t"][min(near[-1] + 1, len(tr["t"]) - 1)]
    ta = _ta()
    ta.time = t0
    ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                   pv0[1][0] + dv0[0], pv0[1][1] + dv0[1], pv0[1][2] + dv0[2]]
    try:
        ta.propagate_until(t0 + t1)
    except Exception:
        return None
    ta.state[3] += dv1[0]
    ta.state[4] += dv1[1]
    ta.state[5] += dv1[2]
    n_fine = 1200
    dt_f = (t_b - t_a) / n_fine
    try:
        ta.propagate_until(t0 + t_a)
    except Exception:
        return None
    best = None
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
            continue
        n_in += 1
        if n_in % 4 != 1:
            continue
        pv_arr = [s6[:3].tolist(), s6[3:].tolist()]
        res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
        if res is None:
            continue
        dv2 = res[0]
        T2 = (t_a + (k + 1) * dt_f) - t1
        dvtot = (np.linalg.norm(dv0) + np.linalg.norm(dv1)
                 + np.linalg.norm(dv2)) * V
        row = [idE, idL, idD, t0, *pv0[0], *pv0[1],
               *list(dv0), *list(dv1), *dv2.tolist(), t1, T2]
        pad = [-1.0] + [0.0] * 20
        chrom = list(row) + pad * (udp.dim // 21 - 1)
        f = udp.fitness(chrom)[0]
        if f >= 0:
            continue
        mass = -f
        if best is None or mass > best[0]:
            rn, vn, e2 = moon_rel(s6)
            best = (mass, row, dict(
                dv_tot=dvtot, dv0=np.linalg.norm(dv0) * V,
                dv1=np.linalg.norm(dv1) * V, dv2=np.linalg.norm(dv2) * V,
                dt_d=(t1 + T2) / DAY, r_arr=rn, v_inf=vn, e2=e2))
    return best


# ------------------------------------------------------------- Phase B3
def phase_b3(udp, idE, idL, idD, cands, n_seed=12, t_max_d=160.0):
    aL, eL, iL = udp.moon_data[idL]
    aE, eE, iE = udp.earth_data[idE]
    pool = [c for c in cands if c["rm_min"] < 3.5e8]
    pool.sort(key=lambda c: c["e2"])
    seen, seeds = set(), []
    for c in pool + sorted(cands, key=lambda c: c["rm_min"]):
        key = (round(c["ea"], 3), round(c["t0"], 3), c["r_apo"])
        if key not in seen:
            seen.add(key)
            seeds.append(c)
    best_overall = None
    for cand in seeds[:n_seed]:
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, cand["ea"])
        dv0 = cand["dv0"].tolist()
        t0, t1 = cand["t0"], cand["t_apo_d"] * DAY
        ta = _ta()
        ta.time = t0
        ta.state[:] = [pv0[0][0], pv0[0][1], pv0[0][2],
                       pv0[1][0] + dv0[0], pv0[1][1] + dv0[1], pv0[1][2] + dv0[2]]
        try:
            ta.propagate_until(t0 + t1)
        except Exception:
            continue
        s_apo = np.array(ta.state[:6])
        v_in = np.array([s_apo[3] - s_apo[1], s_apo[4] + s_apo[0] + MU, s_apo[5]])
        v_hat = v_in / np.linalg.norm(v_in)
        r_e = np.array([s_apo[0] + MU, s_apo[1], s_apo[2]])
        r_hat = r_e / np.linalg.norm(r_e)
        n_hat = np.cross(v_hat, r_hat)
        n_hat /= np.linalg.norm(n_hat)
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
                    pen = max(0.0, (rm_nd * L - aL * (1 + eL)) / 1e5)
                    score = (np.linalg.norm(dv1) * V + dv2p + pen)
                    if best_g is None or score < best_g[0]:
                        best_g = (score, dv1)
        if best_g is None:
            continue
        dv1_g = best_g[1]

        def f_exact(p):
            out = _peri_info(pv0, t0, dv0, p.tolist(), t1, t_max_d)
            if out is None:
                return 1e9
            rm_nd, s6, t_p, tr = out
            if rm_nd * L > aL * (1 + eL):
                return 8000.0 + (rm_nd * L - aL * (1 + eL)) / 1e5
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

        sol = minimize(f_exact, dv1_g, method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 0.5, "maxfev": 220,
                                "disp": False,
                                "initial_simplex": np.array(
                                    [dv1_g] + [dv1_g + 8.0 / V * e
                                               for e in (v_hat, n_hat, r_hat)])})
        if sol.fun > 6000:
            continue
        out = _peri_info(pv0, t0, dv0, sol.x.tolist(), t1, t_max_d)
        if out is None:
            continue
        _, _, _, tr = out
        best = arrival_search(udp, idE, idL, idD, pv0, t0, dv0,
                              sol.x.tolist(), t1, tr, aL, eL, iL)
        if best and (best_overall is None or best[0] > best_overall[0]):
            best_overall = best
    return best_overall


# ------------------------------------------------------------- per-pair driver
def run_pair(pair):
    t0 = time.time()
    udp = LtlTrajectory(BASE)
    idE, idL, idD = pair["idE"], pair["idL"], pair["idD"]
    aL, eL, iL = udp.moon_data[idL]
    out = dict(idE=idE, idL=idL, idD=idD, eL=float(eL),
               iE=pair["iE"], band=pair["band"],
               dv_imp=pair["dv_imp"], mass_imp=pair["mass_imp"])
    cands = phase_a(udp, idE, idL)
    out["n_bound_returns"] = len(cands)
    if not cands:
        out["status"] = "FAIL_no_bound_return"
        out["wall_s"] = round(time.time() - t0, 1)
        return out
    best = phase_b3(udp, idE, idL, idD, cands, n_seed=12)
    if best is None:
        out["status"] = "FAIL_no_valid_capture"
        out["wall_s"] = round(time.time() - t0, 1)
        return out
    mass, row, info = best
    out.update(status="SUCCESS", wsb_mass=float(mass),
               wsb_dv=float(info["dv_tot"]), wsb_dv2=float(info["dv2"]),
               wsb_v_inf=float(info["v_inf"]), wsb_dt_d=float(info["dt_d"]),
               dmass=float(mass - pair["mass_imp"]),
               ddv=float(info["dv_tot"] - pair["dv_imp"]),
               row=[float(v) for v in row])
    out["wall_s"] = round(time.time() - t0, 1)
    return out


def main():
    pairs = json.load(open("/tmp/ch1_e603_pairs.json"))
    print(f"E-603 WSB eL probe: {len(pairs)} pairs, 4 workers", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_pair, p): p for p in pairs}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            tag = r["status"]
            extra = ""
            if r["status"] == "SUCCESS":
                extra = (f" wsb_dv={r['wsb_dv']:.0f} (imp {r['dv_imp']:.0f}) "
                         f"dmass={r['dmass']:+.0f}kg v_inf={r['wsb_v_inf']:.0f}")
            print(f"  [{r['band']:4} eL={r['eL']:.3f} E{r['idE']} L{r['idL']}] "
                  f"{tag}{extra} ({r['wall_s']:.0f}s)", flush=True)
            json.dump(results, open("/tmp/ch1_e603_results.json", "w"), indent=1)
    json.dump(results, open("/tmp/ch1_e603_results.json", "w"), indent=1)

    # ---- band summary ----
    print("\n=== BAND SUMMARY ===", flush=True)
    for band in ("LOW", "HIGH"):
        rs = [r for r in results if r["band"] == band]
        if not rs:
            continue
        succ = [r for r in rs if r["status"] == "SUCCESS"]
        rate = len(succ) / len(rs)
        line = (f"{band}: n={len(rs)} success={len(succ)} "
                f"rate={rate:.0%}")
        if succ:
            wsb_dv = np.median([r["wsb_dv"] for r in succ])
            imp_dv = np.median([r["dv_imp"] for r in succ])
            dmass = np.median([r["dmass"] for r in succ])
            n_pos = sum(r["dmass"] > 0 for r in succ)
            line += (f" | median wsb_dv={wsb_dv:.0f} vs floor {HOHMANN_FLOOR:.0f}"
                     f" vs imp {imp_dv:.0f} | median dmass={dmass:+.0f}kg"
                     f" | dmass>0: {n_pos}/{len(succ)}")
        print(line, flush=True)
    print("\nwrote /tmp/ch1_e603_results.json", flush=True)


if __name__ == "__main__":
    main()
