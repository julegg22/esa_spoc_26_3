"""Extended-TOF polish: re-solve all banked transfers with finer TOF grid
+ t0 (Sun phase) sweep.

Original solver used TOF in {5, 8, 11}. Tests show 15d gives substantial
gains for many inclined-Moon pairs. Optimal TOF varies per pair.

Per banked transfer:
- TOF in (5, 8, 11, 13, 15, 18, 22, 28)
- t0 in (0, π/2, π, 3π/2)
- ea_dep, ea_arr 5x5 grid
- Lambert seed + 3D DC + eccentric arrival

Bank if improved.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric
from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0
from scipy.optimize import least_squares

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


def try_transfer(idE, idL, t0_val, tof_d, ea_dep, ea_arr, raan_e=0.0, argp_e=0.0):
    udp = _UDP[0]
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
    row = [idE, idL, 0, t0_val, *pv0[0], *pv0[1],
            *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
    mass = evaluate_row(row, udp)
    if mass <= 0:
        return None
    return mass, row


def _polish_task(args):
    idx, current_row = args
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])
    current_mass = evaluate_row(current_row, _UDP[0])

    best = (current_mass, current_row)
    # Smaller grid for faster turnaround: focus on TOFs we missed (13, 15, 18)
    for tof_d in (11, 13, 15, 18, 25):
        for t0_val in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
            for ea_dep in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                for ea_arr in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                    res = try_transfer(idE, idL, t0_val, tof_d, ea_dep, ea_arr)
                    if res is not None and res[0] > best[0]:
                        # Set idD from current row
                        new_row = list(res[1])
                        new_row[2] = idD
                        best = (res[0], new_row)

    return idx, best[1], best[0], current_mass


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
    # Estimate
    print(f"Estimated wall: {len(active) * 200 / n_workers / 60:.0f} min on "
          f"{n_workers} workers", flush=True)

    print(f"\nExtended-TOF polish starting...", flush=True)
    t_start = time.time()
    polished = list(dv)
    n_improved = 0
    total_gain = 0

    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _polish_task, active, chunksize=2):
            gain = new_mass - orig_mass
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                n_improved += 1
                total_gain += gain
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg "
                      f"(+{gain:.0f})", flush=True)
            # Save periodically
            if (n_improved + 1) % 20 == 0:
                f_p = udp.fitness(polished)[0]
                if -f_p > baseline_mass + 0.5:
                    bank_path.write_text(json.dumps([{
                        "decisionVector": [float(v) for v in polished],
                        "problem": "trajectory",
                        "challenge": "spoc-4-luna-tomato-logistics",
                    }]))

    wall = time.time() - t_start
    final_mass = -udp.fitness(polished)[0]
    print(f"\nPolish done in {wall:.0f}s: {n_improved}/{len(active)} improved, "
          f"+{total_gain:.0f} kg", flush=True)
    print(f"Final: {final_mass:.0f} kg (was {baseline_mass:.0f})", flush=True)

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
