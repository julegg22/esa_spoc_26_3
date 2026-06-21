"""E-686: TRUE BCP-synodic floor for ONE expensive circular capture (model-mismatch-free).

E-685 showed the cheap Lambert seed (~3900) is a Keplerian-vs-BCP model artifact (target sits
6509 km off the synodic Moon over a 50d arc). This solves the capture CONSISTENTLY in the BCP
synodic frame: target moon_orbit_state (a state ON the LLO in synodic coords) directly, favor SHORT
tof (3-10d, where the arc is barely Sun-perturbed so models agree), DC the departure burn dv0 to hit
the synodic LLO position, then solve_arrival_dv -> dv2, verify under official udp.fitness.

Grid over departure phasing (raan_e, ea_e), arrival LLO point (raan_m, ea_m), short tof; keep the
min VALID total dv. DECISIVE for pair (241,50), bank 6617:
  min BCP dv << 6617 -> real headroom (bank's circular captures ARE improvable) -> lever alive.
  min BCP dv ~ 6617  -> bank at the true BCP floor -> circular captures intrinsically expensive -> lever closes.

Usage: python ch1_bcp_synodic_solve.py [idE=241] [idL=50]
"""
import sys, json, time, math, itertools
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import (LtlTrajectory, earth_orbit_state, moon_orbit_state,
                                        propagate, T, V, L)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def dv_from_mass(m):
    return -311.0 * 9.80665 * math.log((m + 500.0) / 5000.0) if m > 0 else float("nan")


def try_combo(udp, idE, idL, aE, eE, iE, aM, eM, iM, raan_e, ea_e, raan_m, ea_m, tof_d):
    tof_nd = tof_d * 86400 / T
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, 0.0, ea_e)
    tgt = moon_orbit_state(aM, eM, iM, raan_m, 0.0, ea_m)
    p_target = np.array(tgt[0])

    def resid(dv0):
        pv1 = propagate(pv0, 0.0, [list(dv0), [0, 0, 0], [0, 0, 0]], [tof_nd, 0.0])
        if len(pv1) == 0:
            return np.array([30.0, 30.0, 30.0])
        return np.array(pv1[0]) - p_target

    # seed dv0: rough impulse toward the Moon (scaled). small synodic magnitude.
    seed = (p_target - np.array(pv0[0])) / tof_nd - np.array(pv0[1])
    seed = np.clip(seed, -3, 3)
    try:
        sol = least_squares(resid, seed.tolist(), method="trf", xtol=1e-11, max_nfev=120)
    except Exception:
        return None
    dv0 = sol.x
    pv1 = propagate(pv0, 0.0, [dv0.tolist(), [0, 0, 0], [0, 0, 0]], [tof_nd, 0.0])
    if len(pv1) == 0:
        return None
    if np.linalg.norm(np.array(pv1[0]) - p_target) * L > 5000.0:   # didn't converge within 5000 km
        return None
    a2 = solve_arrival_dv(pv1, aM, eM, iM)
    if a2 is None:
        return None
    dv2 = a2[0]
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1], *dv0.tolist(), 0., 0., 0., *np.asarray(dv2).tolist(),
           float(tof_nd), 0.0]
    f = udp.fitness(row)
    if f[0] >= 0:
        return None
    return dv_from_mass(-f[0])


def main(idE=241, idL=50):
    print("[E-686] init: heyoka BCP + orbits ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    Vunit = 3.84405e8 / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    bdv = float("nan")
    for i in range(0, len(bank), 21):
        if int(bank[i]) == idE and int(bank[i + 1]) == idL:
            r = bank[i:i + 21]
            bdv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
    raan_e_g = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    ea_e_g = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    raan_m_g = np.linspace(0, 2 * np.pi, 4, endpoint=False)
    ea_m_g = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    tof_g = [3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    combos = list(itertools.product(raan_e_g, ea_e_g, raan_m_g, ea_m_g, tof_g))
    print(f"[E-686] pair ({idE},{idL}) eM={eM:.3f} bank_dv={bdv:.0f} | {len(combos)} combos (synodic-LLO DC, short tof)", flush=True)
    best = float("inf"); t0 = time.time(); valid = 0
    for k, (re_, ee_, rm_, em_, tof_d) in enumerate(combos):
        r = try_combo(udp, idE, idL, aE, eE, iE, aM, eM, iM, re_, ee_, rm_, em_, tof_d)
        if r is not None and r < best:
            best = r; valid += 1
            print(f"  NEW BEST dv={best:.0f} (bank {bdv:.0f}) tof={tof_d}d [{k}/{len(combos)} {time.time()-t0:.0f}s]", flush=True)
        if k % 200 == 0 and k > 0:
            print(f"  .. {k}/{len(combos)} best={best if best<1e9 else None} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-686] VERDICT pair ({idE},{idL}): min BCP-synodic dv = {best:.0f} vs bank {bdv:.0f}  (Δ={bdv-best:+.0f})", flush=True)
    print("  << bank -> real headroom on circular captures -> lever ALIVE", flush=True)
    print("  ~ bank -> bank at true BCP floor -> circular captures intrinsically expensive -> lever closes", flush=True)


if __name__ == "__main__":
    e = int(sys.argv[1]) if len(sys.argv) > 1 else 241
    l = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    main(e, l)
