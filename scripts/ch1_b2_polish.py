"""B2 polish: extended (raan_l, argp_l) sweep on banked transfers.

The audit (B2) found that pv_tgt is over-constrained at raan_l=argp_l=0.
The spec lets these be free. Adding them to the sweep gives DC more
arrival-point options → may find lower-dv configurations.

For each banked transfer, sweep the existing C-022 grid PLUS
(raan_l × argp_l) extra dofs. Keep result iff mass improves.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V

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


def _task(args):
    """Sweep (raan_e × argp_e × ea_dep × t0 × raan_l × argp_l × ea_arr × t2_d)."""
    idx, current_row, current_mass = args
    udp = _UDP[0]
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])
    best = (current_mass, current_row)
    # Reduced grid for raan_e × argp_e × ea_dep × t0 (the existing axes)
    # Added: raan_l (4) and argp_l (2)
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for ea_dep in (0.0, np.pi):
            for t0_val in (0.0, np.pi):
                for raan_l in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                    for argp_l in (0.0, np.pi):
                        for ea_arr in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                            for t2_d in (0.5, 1.2):
                                res = try_bcp_apogee_3impulse(
                                    udp, idE, idL, raan_e, 0.0, ea_dep,
                                    t0_val, raan_l, argp_l, ea_arr,
                                    t2_d=t2_d)
                                if res is not None and res[0] > best[0]:
                                    new_row = list(res[1])
                                    new_row[2] = idD
                                    best = (res[0], new_row)
    return idx, best[1], best[0], current_mass


def main(n_workers=8):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    bank = json.load(open(bank_path))
    dv = bank[0]["decisionVector"]
    active = []
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            row = dv[i:i + 21]
            m = evaluate_row(row, udp)
            active.append((i // 21, row, m))
    baseline = -udp.fitness(dv)[0]
    print(f"{len(active)} transfers, baseline {baseline:.0f}kg", flush=True)
    grid_size = 4 * 1 * 2 * 2 * 4 * 2 * 4 * 2
    print(f"Grid: {grid_size} ICs/pair, est wall: "
          f"~{len(active) * grid_size * 0.3 / n_workers / 60:.0f}min",
          flush=True)
    t0 = time.time()
    polished = list(dv)
    n_imp = 0
    total_gain = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _task, active, chunksize=1):
            gain = new_mass - orig_mass
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                n_imp += 1
                total_gain += gain
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg "
                      f"(+{gain:.0f})", flush=True)
                if n_imp % 5 == 0:
                    bank_path.write_text(json.dumps([{
                        "decisionVector": [float(v) for v in polished],
                        "problem": "trajectory",
                        "challenge": "spoc-4-luna-tomato-logistics"}]))
    f_p = -udp.fitness(polished)[0]
    print(f"\n{n_imp}/{len(active)} improved, +{total_gain:.0f}kg "
          f"in {time.time() - t0:.0f}s", flush=True)
    if f_p > baseline + 0.5:
        bank_path.write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics"}]))
        print(f"BANKED: {baseline:.0f} → {f_p:.0f}kg", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
