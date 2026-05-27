"""Polish bank with EXTENDED t2_d sweep (0.3, 0.7, 1.2, 2.0, 3.0, 5.0).

Discovery during B1 validation: the bank's (8, 175) at 599 kg jumped to
838 kg (+239) when t2_d=3.0 was added to the sweep. The existing solver
(track_to_perilune) with longer T2 coast catches better arrival geometries
for high-eL Moon targets where the orbit's period is several days.

This polish:
- targets the 165 banked transfers with dv1 > 500 m/s (= bank's "high
  plane-change" pairs — most likely to benefit from a wider sweep)
- adds t2_d ∈ {2.0, 3.0, 5.0} to the existing {0.3, 0.7, 1.2}
- keeps existing C-022 architecture (track_to_perilune); does NOT use
  the B1 apolune variant (which validation showed is functionally
  identical to perilune for these geometries)

Per-pair: 4×2×4×2×4×6 = 1536 ICs (twice the original 576). On 8 workers
that's ~5 min/pair × 165 / 8 ≈ 100 min. Run in background.
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
    chr_p = list(row)
    pad = (udp.dim - len(chr_p)) // 21
    for _ in range(pad):
        chr_p.extend([-1.0] + [0.0] * 20)
    return -udp.fitness(chr_p)[0]


def _task(args):
    idx, current_row, current_mass = args
    udp = _UDP[0]
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])
    best = (current_mass, current_row)
    # 4 × 2 × 4 × 2 × 4 × 6 = 1536 ICs (existing + extended t2_d)
    for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                for t0_val in (0.0, np.pi):
                    for ea_arr in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                        # EXTENDED t2_d
                        for t2_d in (0.3, 0.7, 1.2, 2.0, 3.0, 5.0):
                            res = try_bcp_apogee_3impulse(
                                udp, idE, idL, raan_e, argp_e, ea_dep,
                                t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
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
            row = list(dv[i:i + 21])
            dv1 = np.linalg.norm(row[13:16]) * V  # SI m/s
            m = evaluate_row(row, udp)
            active.append((i // 21, row, m, dv1))

    # Select transfers with dv1 > 500 m/s (most polish potential)
    targets = [(idx, row, m) for idx, row, m, dv1 in active if dv1 > 500]
    print(f"Bank: {len(active)} transfers, polishing {len(targets)} with dv1 > 500 m/s",
           flush=True)
    baseline = -udp.fitness(dv)[0]
    grid = 4 * 2 * 4 * 2 * 4 * 6
    print(f"Grid: {grid} ICs/pair, est wall: "
          f"~{len(targets) * grid * 0.3 / n_workers / 60:.0f}min", flush=True)
    t0 = time.time()
    polished = list(dv)
    n_imp = 0
    total_gain = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _task, targets, chunksize=1):
            gain = new_mass - orig_mass
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                n_imp += 1
                total_gain += gain
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg "
                      f"(+{gain:.0f})", flush=True)
                if n_imp % 3 == 0:
                    bank_path.write_text(json.dumps([{
                        "decisionVector": [float(v) for v in polished],
                        "problem": "trajectory",
                        "challenge": "spoc-4-luna-tomato-logistics"}]))
    f_p = -udp.fitness(polished)[0]
    print(f"\n{n_imp}/{len(targets)} improved, +{total_gain:.0f}kg "
          f"in {time.time() - t0:.0f}s", flush=True)
    if f_p > baseline + 0.5:
        bank_path.write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics"}]))
        print(f"BANKED: {baseline:.0f} → {f_p:.0f}kg", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
