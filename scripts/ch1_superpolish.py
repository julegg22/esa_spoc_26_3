"""Super-polish: optimize each banked transfer over ALL angular DOF.

Current 156 transfers have median dv 5414 m/s (Hohmann ~3950).
The 1500 m/s excess comes from sub-optimal (raan_e, argp_e, ea_dep, ea_arr, tof).

Per-transfer optimization:
- Free vars: raan_e, argp_e, ea_dep, ea_arr, tof_d, t0 (Sun phase) = 6 angular
- Inner: re-solve trajectory via Lambert+3D-DC at each candidate point
- Objective: maximize delivered mass via UDP fitness

Uses scipy Nelder-Mead. Per-transfer ~10-30s. Total ~5-10min on 8 workers.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
from scipy.optimize import minimize, least_squares
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric
from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def evaluate_row(row, udp):
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    return -udp.fitness(chr_padded)[0]


def solve_trajectory(udp, idE, idL, idD, raan_e, argp_e, ea_dep, ea_arr,
                       tof_d, t0_val):
    """Build trajectory from angular params via Lambert+3D-DC."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
    tof = tof_d * 86400.0 / T

    dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)) or np.linalg.norm(dv0_seed) > 15:
        return None

    def residual(p):
        pv_a = propagate(pv0, t0_val, [p.tolist(), [0, 0, 0], [0, 0, 0]],
                          [tof, 0.0])
        if len(pv_a) == 0:
            return [100.0] * 3
        return [pv_a[0][0] - pv_tgt[0][0],
                pv_a[0][1] - pv_tgt[0][1],
                pv_a[0][2] - pv_tgt[0][2]]

    try:
        sol = least_squares(residual, dv0_seed, method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=50)
    except Exception:
        return None
    dv0 = sol.x
    pv_arr = propagate(pv0, t0_val, [dv0.tolist(), [0, 0, 0], [0, 0, 0]],
                        [tof, 0.0])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, idD, t0_val, *pv0[0], *pv0[1],
            *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
    mass = evaluate_row(row, udp)
    if mass <= 0:
        return None
    return mass, row


def superpolish_row(row, idE, idL, idD, orig_mass):
    """Optimize 6 angular DOF, keeping idE/idL/idD fixed."""
    udp = _UDP[0]

    # Extract current angular params from the row's pv0
    pv0_x = row[4]
    pv0_y = row[5]
    pv0_z = row[6]
    # Roughly estimate ea_dep from position (not exact but OK as initial guess)
    # For simplicity, just start at ea_dep = 0
    x0_angles = np.array([0.0, 0.0, 0.0, 0.0, (row[19] + row[20]) * T / 86400.0, row[3]])

    def neg_mass(p):
        raan_e, argp_e, ea_dep, ea_arr, tof_d, t0_val = p
        if tof_d < 2 or tof_d > 20:
            return -orig_mass + 0.1  # discourage but allow
        res = solve_trajectory(udp, idE, idL, idD, raan_e, argp_e,
                                  ea_dep, ea_arr, tof_d, t0_val)
        if res is None:
            return -orig_mass + 0.1
        return -res[0]

    # Multi-start: try several initial points
    best_mass = orig_mass
    best_row = row
    starts = [
        [0.0, 0.0, 0.0, 0.0, 11.0, 0.0],
        [0.0, 0.0, np.pi, np.pi, 11.0, 0.0],
        [0.0, 0.0, np.pi/2, np.pi/2, 8.0, 0.0],
        [np.pi/2, 0.0, 0.0, 0.0, 11.0, np.pi],
        [np.pi, 0.0, np.pi, 0.0, 11.0, 0.0],
    ]
    for start in starts:
        try:
            sol = minimize(neg_mass, np.array(start), method="Nelder-Mead",
                            options={"xatol": 1e-3, "fatol": 0.5,
                                      "maxiter": 80, "disp": False})
        except Exception:
            continue
        if -sol.fun > best_mass:
            # Verify
            raan_e, argp_e, ea_dep, ea_arr, tof_d, t0_val = sol.x
            res = solve_trajectory(udp, idE, idL, idD, raan_e, argp_e,
                                      ea_dep, ea_arr, tof_d, t0_val)
            if res is not None and res[0] > best_mass:
                best_mass = res[0]
                best_row = res[1]

    return best_row, best_mass, orig_mass


def _polish_task(args):
    idx, row = args
    idE = int(row[0])
    idL = int(row[1])
    idD = int(row[2])
    orig_mass = evaluate_row(row, _UDP[0])
    return idx, *superpolish_row(row, idE, idL, idD, orig_mass)


def main(n_workers=8):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    bank = json.load(open(bank_path))
    dv = bank[0]["decisionVector"]

    active = [(i // 21, dv[i:i + 21]) for i in range(0, len(dv), 21)
              if dv[i] >= 0]
    print(f"Bank has {len(active)} active transfers", flush=True)

    baseline_mass = -udp.fitness(dv)[0]
    print(f"Baseline mass: {baseline_mass:.0f} kg", flush=True)

    print(f"\nSuper-polish on {n_workers} workers...", flush=True)
    t_start = time.time()
    polished = list(dv)
    total_gain = 0
    n_improved = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _polish_task, active, chunksize=2):
            gain = new_mass - orig_mass
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                n_improved += 1
                total_gain += gain
                if gain > 50:
                    print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg "
                          f"(+{gain:.0f})", flush=True)
    wall = time.time() - t_start

    print(f"\nSuper-polish done in {wall:.0f}s: "
          f"{n_improved}/{len(active)} improved, +{total_gain:.0f} kg", flush=True)
    final_mass = -udp.fitness(polished)[0]
    print(f"New total: {final_mass:.0f} kg (was {baseline_mass:.0f})", flush=True)

    if final_mass > baseline_mass + 0.5:
        bank_path.write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics",
        }]))
        print(f"BANKED: {baseline_mass:.0f} → {final_mass:.0f} kg "
              f"(+{final_mass - baseline_mass:.0f})", flush=True)


if __name__ == "__main__":
    n_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=n_workers)
