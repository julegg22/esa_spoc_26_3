"""Full-matrix feasibility scan: which (idE, idL) of 160k have ANY Hohmann hit?

Per-pair: try 8 simple Hohmann seeds (raan_e × ea_dep × t0). For each,
quickly check if Hohmann trajectory reaches Moon SOI within target's
r-range. NO DC, NO optimization — just feasibility tagging.

Output: matrix of (idE, idL) → bool (feasible) + best perilune distance
found across the 8 seeds. Saves to runs/ch1/feasibility_matrix.json.

Used to validate: are the 'unused' idEs/idLs truly architecturally
infeasible, or did Hungarian miss feasible pairings?
"""
import sys
import time
import json
import math
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    LtlTrajectory, L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state,
)
from esa_spoc_26.ch1_trajectory_solve import _ta, track_to_perilune

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3
ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _hohmann_dv0_synbasis(pv0):
    [x, y, z], [vx, vy, vz] = pv0
    rx, ry, rz = (x + MU) * L, y * L, z * L
    r0 = math.sqrt(rx * rx + ry * ry + rz * rz)
    vx_e, vy_e, vz_e = (vx - y) * V, ((vy + x) + MU) * V, vz * V
    v_mag = math.sqrt(vx_e * vx_e + vy_e * vy_e + vz_e * vz_e)
    a_t = (r0 + R_MOON_SI) / 2.0
    v_peri = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
    scale = (v_peri - v_mag) / v_mag
    return [vx_e * scale / V, vy_e * scale / V, vz_e * scale / V]


def _task(args):
    """Returns (idE, idL, best_r_min_m). best_r_min = closest perilune across 8 seeds."""
    idE, idL = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    r_apo_target = aL * (1.0 + eL)
    t_max_nd = 25.0 * 86400.0 / T

    best_r_min = float('inf')
    # 8 Hohmann seeds: raan_e × ea_dep × t0 (each 2 values)
    for raan_e in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        for ea_dep in (0.0, math.pi):
            pv0 = earth_orbit_state(aE, eE, iE, raan_e, 0.0, ea_dep)
            dv0 = _hohmann_dv0_synbasis(pv0)
            for t0 in (0.0, math.pi):
                try:
                    _, _, r_min, imp = track_to_perilune(
                        pv0, t0, dv0, t_max_nd)
                except Exception:
                    continue
                if imp:
                    continue
                if r_min < best_r_min:
                    best_r_min = r_min
    return idE, idL, best_r_min, r_apo_target


def main(n_workers=8,
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/feasibility_matrix.json"):
    udp = LtlTrajectory(ROOT)
    pairs = [(ie, il) for ie in range(400) for il in range(400)]
    print(f"Scanning {len(pairs)} (idE, idL) pairs for Hohmann feasibility...",
           flush=True)
    print(f"Est wall: 8 props/pair × ~0.1 sec = ~{len(pairs) * 8 * 0.1 / n_workers / 60:.0f} min",
           flush=True)

    t_start = time.time()
    results = {}  # (idE, idL) → (best_r_min, r_apo_target, feasible_bool)
    n_done = 0
    n_feas = 0  # pairs where best_r_min < r_apo (could reach orbit r-range)
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, r_min, r_apo in p.imap_unordered(_task, pairs,
                                                          chunksize=20):
            n_done += 1
            feasible = r_min < r_apo  # spacecraft reaches within target orbit
            if feasible:
                n_feas += 1
            results[(idE, idL)] = (r_min, r_apo, feasible)
            if n_done % 5000 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                print(f"  [{n_done:6d}/{len(pairs)}] feasible={n_feas} "
                      f"({n_feas/n_done*100:.1f}%) wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)

    # Save as compact JSON
    serializable = {f"{k[0]},{k[1]}": [float(v[0]), float(v[1]), bool(v[2])]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    print(f"\nScan done in {time.time()-t_start:.0f}s", flush=True)
    print(f"Total feasible (any Hohmann seed reaches target r-range): "
          f"{n_feas} / {len(pairs)} ({n_feas/len(pairs)*100:.1f}%)", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=nw)
