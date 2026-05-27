"""Quick B2 test on 10 lowest-mass banked transfers."""
import sys, time, json
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
from esa_spoc_26.ch1_trajectory import LtlTrajectory

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def evaluate_row(row, udp):
    n = len(row) // 21
    chr_p = list(row)
    for _ in range(400 - n):
        chr_p.extend([-1.0] + [0.0] * 20)
    return -udp.fitness(chr_p)[0]


def _task(args):
    idx, current_row, current_mass = args
    udp = _UDP[0]
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])
    best_mass = current_mass
    best_row = current_row
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
                                if res is not None and res[0] > best_mass:
                                    best_mass = res[0]
                                    nr = list(res[1])
                                    nr[2] = idD
                                    best_row = nr
    return idx, best_mass, current_mass


def main():
    udp = LtlTrajectory(ROOT)
    bank = json.load(open('/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json'))
    dv = bank[0]['decisionVector']
    active = []
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            row = list(dv[i:i + 21])
            m = evaluate_row(row, udp)
            active.append((i // 21, row, m))
    active.sort(key=lambda x: x[2])
    bottom = active[:10]
    print(f"Polishing 10 lowest-mass transfers:", flush=True)
    for idx, row, m in bottom:
        print(f"  idx={idx} idE={int(row[0])} idL={int(row[1])} mass={m:.0f}",
               flush=True)
    t0 = time.time()
    with mp.Pool(8, initializer=_init) as p:
        for idx, new_mass, orig_mass in p.imap_unordered(_task, bottom,
                                                            chunksize=1):
            print(f"  [{idx:3d}] orig {orig_mass:>6.0f} → new {new_mass:>6.0f} "
                  f"(Δ {new_mass - orig_mass:>+6.0f})", flush=True)
    print(f"Total wall: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
