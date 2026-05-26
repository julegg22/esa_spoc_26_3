"""Very-long-TOF (60-150d) polish — explore WSB / Sun-assist regime.

Sun has period ~30 days in BCP. Long TOFs (60-150d) span multiple Sun
cycles, possibly enabling ballistic capture / weak-stability transfers.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')

from ch1_long_tof_test import try_long_tof_transfer, _init, evaluate_row
from esa_spoc_26.ch1_trajectory import LtlTrajectory

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def _task(args):
    idx, current_row, current_mass = args
    from ch1_long_tof_test import _UDP
    udp = _UDP[0]
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])
    best = (current_mass, current_row)
    # Very long TOFs spanning multiple Sun cycles
    for tof_d in (60, 80, 100, 120, 150):
        for t0_val in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            for ea_dep in np.linspace(0, 2 * np.pi, 3, endpoint=False):
                for ea_arr in np.linspace(0, 2 * np.pi, 3, endpoint=False):
                    res = try_long_tof_transfer(idE, idL, tof_d, t0_val,
                                                   ea_dep, ea_arr)
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
