"""WSB Tier 0 — confirmation experiment for low-energy transfers in BCP.

For 10 selected LEO+LMO bank transfers with current mass ∈ [300, 700] kg,
sweep:
  - dv0 magnitude scaling: {0.93, 0.96, 0.99, 1.00, 1.02, 1.05} × Hohmann
  - dv0 tilt angle off-prograde: 0, ±5°, ±10° in two orthogonal directions
  - TOF (= T1): {30, 45, 60, 80, 100} days
For each (scale, tilt, TOF) combo:
  - Propagate full BCP from pv0 with dv0
  - Find ALL local perilune passes (multi-rev)
  - At each perilune, evaluate `solve_arrival_eccentric`
  - Record mass; keep best per pair

Success criterion: at least 1 pair improves > 100 kg over bank.
That validates BCP dynamics support ballistic capture *in this problem*.

Compute: 10 pairs × 6 scale × 9 tilt × 5 TOF = 2700 configs × ~10s BCP
propagate (100-day average) ≈ 7.5 hours wall on 8 workers.

Usage: nohup python ch1_wsb_tier0.py > runs/ch1/61_wsb_tier0.log 2>&1 &
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    LtlTrajectory, L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state,
)
from esa_spoc_26.ch1_trajectory_solve import _ta
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _hohmann_dv0(pv0):
    x, y, z = pv0[0]
    vx, vy, vz = pv0[1]
    rx, ry, rz = (x + MU) * L, y * L, z * L
    r0 = np.sqrt(rx ** 2 + ry ** 2 + rz ** 2)
    vx_e, vy_e, vz_e = (vx - y) * V, ((vy + x) + MU) * V, vz * V
    v_mag = np.sqrt(vx_e ** 2 + vy_e ** 2 + vz_e ** 2)
    a_t = (r0 + R_MOON_SI) / 2
    v_peri = np.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
    scale = (v_peri - v_mag) / v_mag
    return np.array([vx_e * scale, vy_e * scale, vz_e * scale]) / V


def scan_perilune_passes(pv0, t0, dv0, t_max_d, dt_d=0.5):
    """Walk BCP; collect (t_d, state) at each local min of r_moon(t)."""
    ta = _ta()
    ta.time = t0
    ta.state[0] = pv0[0][0]
    ta.state[1] = pv0[0][1]
    ta.state[2] = pv0[0][2]
    ta.state[3] = pv0[1][0] + dv0[0]
    ta.state[4] = pv0[1][1] + dv0[1]
    ta.state[5] = pv0[1][2] + dv0[2]
    t_max_nd = t_max_d * 86400.0 / T
    dt_nd = dt_d * 86400.0 / T
    n = int(t_max_nd / dt_nd) + 1
    RE2 = ((6378e3 + 99000) / L) ** 2
    RM2 = ((1737400 + 30000) / L) ** 2
    hist = []
    for k in range(1, n + 1):
        try:
            ta.propagate_until(t0 + k * dt_nd)
        except Exception:
            break
        x, y, z = ta.state[0], ta.state[1], ta.state[2]
        if (x + MU) ** 2 + y * y + z * z < RE2:
            break
        if (x - 1 + MU) ** 2 + y * y + z * z < RM2:
            break
        r = np.sqrt((x - 1 + MU) ** 2 + y * y + z * z)
        hist.append((k, r, ta.state.copy()))
    # local minima
    events = []
    for i in range(1, len(hist) - 1):
        if hist[i][1] < hist[i - 1][1] and hist[i][1] < hist[i + 1][1]:
            events.append((hist[i][0] * dt_d, hist[i][2], hist[i][1] * L))
    return events


def probe_with_tilt(pv0, t0, dv0_nominal, idE, idL, aL, eL, iL):
    """Sweep (scale, tilt, TOF). Return best (mass, dv_total_ms, tof_d)."""
    udp = _UDP[0]
    dv0_mag = np.linalg.norm(dv0_nominal)
    if dv0_mag < 1e-6:
        return None
    dv0_hat = dv0_nominal / dv0_mag
    # Orthogonal basis around dv0_hat
    if abs(dv0_hat[0]) < 0.9:
        u = np.array([1.0, 0.0, 0.0])
    else:
        u = np.array([0.0, 1.0, 0.0])
    e1 = np.cross(dv0_hat, u)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(dv0_hat, e1)

    best = None  # (mass, dv_tot, tof_d)
    for scale in (0.93, 0.96, 0.99, 1.00, 1.02, 1.05):
        for tilt_deg in (0.0, 5.0, -5.0, 10.0, -10.0):
            for tilt_axis_idx in (0, 1):
                tilt = np.radians(tilt_deg)
                if tilt_axis_idx == 0:
                    direction = dv0_hat * np.cos(tilt) + e1 * np.sin(tilt)
                else:
                    direction = dv0_hat * np.cos(tilt) + e2 * np.sin(tilt)
                dv0 = direction * dv0_mag * scale
                if np.linalg.norm(dv0) > 8:
                    continue
                for tof_d in (30.0, 45.0, 60.0, 80.0, 100.0):
                    events = scan_perilune_passes(pv0, t0, dv0.tolist(), tof_d)
                    for t_d, state, r_min_m in events:
                        pv_arr = [list(state[:3]), list(state[3:6])]
                        res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
                        if res is None:
                            continue
                        dv2, _ = res
                        if not np.all(np.isfinite(dv2)) or np.linalg.norm(dv2) > 5:
                            continue
                        T1 = t_d * 86400.0 / T
                        row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
                                *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(),
                                T1, 0.0]
                        chr_p = list(row)
                        pad = (udp.dim - len(chr_p)) // 21
                        for _ in range(pad):
                            chr_p.extend([-1.0] + [0.0] * 20)
                        f = udp.fitness(chr_p)[0]
                        if f >= 0:
                            continue
                        mass = -f
                        dv_tot = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
                        if best is None or mass > best[0]:
                            best = (mass, dv_tot, t_d, row)
    return best


def _task(args):
    idE, idL, current_mass = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    # 4 ea_dep × 2 t0 = 8 starting geometries
    for ea_dep in (0, np.pi / 2, np.pi, 3 * np.pi / 2):
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
        dv0_nominal = _hohmann_dv0(pv0)
        if not np.all(np.isfinite(dv0_nominal)):
            continue
        for t0 in (0.0, np.pi):
            res = probe_with_tilt(pv0, t0, dv0_nominal, idE, idL, aL, eL, iL)
            if res is not None and (best is None or res[0] > best[0]):
                best = res
    return idE, idL, current_mass, best


def main(n_workers=8):
    udp = LtlTrajectory(ROOT)
    bank = json.load(open('/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json'))
    dv = bank[0]['decisionVector']
    # Pick LEO+LMO transfers with mass 300-700
    candidates = []
    for i in range(0, len(dv), 21):
        if dv[i] < 0:
            continue
        idE, idL = int(dv[i]), int(dv[i + 1])
        aE = udp.earth_data[idE, 0]
        aL = udp.moon_data[idL, 0]
        if aE > 1.5e7 or aL > 3e6:  # only LEO + LMO
            continue
        row = list(dv[i:i + 21])
        chr_p = list(row) + [-1.0] * 20 * (400 - 1)
        chr_p = chr_p[:udp.dim]
        m = -udp.fitness(chr_p)[0]
        if 300 < m < 700:
            candidates.append((idE, idL, m))
    candidates.sort(key=lambda x: x[2])
    selected = candidates[:10]
    print(f"Selected 10 LEO+LMO pairs (300-700 kg) for WSB probe:", flush=True)
    for idE, idL, m in selected:
        print(f"  ({idE:>3}, {idL:>3}) bank={m:.0f} kg", flush=True)
    print(f"\nProbe per pair: 8 starts × 6 scale × 5 tilt × 2 axes × 5 TOF = 2400 configs",
           flush=True)

    t_start = time.time()
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, cur_m, best in p.imap_unordered(_task, selected,
                                                          chunksize=1):
            if best is None:
                print(f"  ({idE:>3},{idL:>3}) bank={cur_m:.0f} → FAIL "
                      f"[{time.time() - t_start:.0f}s elapsed]",
                      flush=True)
            else:
                mass, dv_tot, tof_d, _ = best
                gain = mass - cur_m
                print(f"  ({idE:>3},{idL:>3}) bank={cur_m:.0f} → new={mass:.0f} "
                      f"(Δ {gain:+.0f}, dv={dv_tot:.0f}, tof={tof_d:.0f}d) "
                      f"[{time.time() - t_start:.0f}s]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
