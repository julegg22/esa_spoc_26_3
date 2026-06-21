"""E-685: STRONGER (6-DOF, midcourse) BCP differential-correction for the expensive CIRCULAR captures.

E-684 found their 2-body Lambert seeds are ~3900 m/s (bank ~6000+), but lambert_dc (dv0-only)
fails to converge the long BCP arc onto the LLO ('endpoint not near LLO' = arrival radius misses
the circular orbit's single-radius window). FIX: add a MIDCOURSE burn dv1 at t=tof*split, giving
the DC 6-DOF to steer the endpoint onto r_arr_syn (radius a_m). Then solve_arrival_dv -> dv2; score
the full 3-burn row under the OFFICIAL udp.fitness. Try splits {0.3,0.5,0.7}, keep best realized dv.

DECISIVE: does it realize a cheap (<~4500) BCP trajectory beating the bank on the expensive circular
pairs? YES -> the bank's expensive circular captures ARE solver failures -> lever PROVEN (+~74k).
NO -> the cheap Lambert isn't BCP-realizable (Sun cost real) -> bank near floor, lever closes.

Usage: python ch1_circular_dc6.py
"""
import sys, json, time, math
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, earth_orbit_state, propagate, T, V
from esa_spoc_26.ch1_traj_lambert_dc import best_lambert_seed, inertial_to_synodic_pos
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
ROOT = "/home/julian/Projects/esa_spoc_26_3"
PAIRS = [(241, 50), (139, 31), (354, 305), (334, 312), (244, 105), (249, 22)]


def dv_from_mass(m):
    return -311.0 * 9.80665 * math.log((m + 500.0) / 5000.0) if m > 0 else float("nan")


def dc6(udp, idE, idL, seed, split):
    """6-DOF DC: optimize [dv0(3), dv1mid(3)] so the BCP endpoint hits r_arr_syn (radius a_m).
    Midcourse dv1 applied at t = tof*split. Returns realized total dv (official fitness) or None."""
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    raan_e, argp_e, ea_e = seed["raan_e"], seed["argp_e"], seed["ea_e"]
    tof_nd = seed["tof_d"] * 86400 / T
    t1 = tof_nd * split
    t2 = tof_nd * (1.0 - split)
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_e)
    r_arr_syn = inertial_to_synodic_pos(seed["r_arr"], tof_nd)
    dv0_seed = (np.asarray(seed["dv1"]) / V)

    def resid(x):
        dv0 = x[:3].tolist(); dv1 = x[3:6].tolist()
        pv1 = propagate(pv0, 0.0, [dv0, dv1, [0, 0, 0]], [t1, t2])
        if len(pv1) == 0:
            return np.array([50.0, 50.0, 50.0])
        return np.array(pv1[0]) - r_arr_syn

    x0 = np.concatenate([dv0_seed, np.zeros(3)])
    try:
        sol = least_squares(resid, x0, method="trf", xtol=1e-12, max_nfev=300)
    except Exception:
        return None
    dv0 = sol.x[:3]; dv1 = sol.x[3:6]
    pv1 = propagate(pv0, 0.0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]], [t1, t2])
    if len(pv1) == 0:
        return None
    res2 = solve_arrival_dv(pv1, aM, eM, iM)
    if res2 is None:
        return None
    dv2 = res2[0]
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
           *dv0.tolist(), *dv1.tolist(), *np.asarray(dv2).tolist(),
           float(t1), float(t2)]
    f = udp.fitness(row)
    if f[0] >= 0:                       # fitness returns [0] (rejected) or [-mass]
        return None
    mass = -f[0]
    return dv_from_mass(mass), mass


def main():
    print("[E-685] init: heyoka BCP + orbits ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    Vunit = 3.84405e8 / 3.7567696752e5
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    bankdv = {}
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]
        bankdv[(int(r[0]), int(r[1]))] = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
    print(f"[E-685] 6-DOF midcourse DC on {len(PAIRS)} expensive circular pairs; splits 0.3/0.5/0.7", flush=True)
    print(f"  {'pair':>12} {'bank_dv':>8} {'lam_seed':>8}  {'dc6_dv':>8} {'Δvs_bank':>8} {'beats?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0; tot = 0.0
    for e, l in PAIRS:
        seed = best_lambert_seed(udp, e, l)
        bdv = bankdv.get((e, l), float("nan"))
        if seed is None:
            print(f"  ({e:>4},{l:>4}) {bdv:8.0f} {'NO-SEED':>8}", flush=True)
            continue
        best = None
        for split in (0.3, 0.5, 0.7):
            r = dc6(udp, e, l, seed, split)
            if r is not None and (best is None or r[0] < best[0]):
                best = r
        if best is None:
            print(f"  ({e:>4},{l:>4}) {bdv:8.0f} {seed['total']:8.0f}  {'DC6-FAIL':>8} {'':>8} {'no':>7} [{time.time()-t0:.0f}s]", flush=True)
            continue
        ddv = bdv - best[0]
        hit = ddv > 50
        wins += hit; tot += max(ddv, 0)
        print(f"  ({e:>4},{l:>4}) {bdv:8.0f} {seed['total']:8.0f}  {best[0]:8.0f} {ddv:+8.0f} {'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-685] VERDICT: {wins}/{len(PAIRS)} expensive circular pairs beaten by 6-DOF DC; mean Δdv={tot/len(PAIRS):.0f}", flush=True)
    print("  >0 -> bank's expensive circular captures are SOLVER failures -> lever PROVEN, scale + guard-bank", flush=True)
    print("  0  -> cheap Lambert NOT BCP-realizable (Sun cost real) -> bank near floor, lever closes", flush=True)


if __name__ == "__main__":
    main()
