"""TIER 1 of the feasibles-eval pipeline: light mass screen, no DC.

For each NEW feasible (idE, idL) from the matrix scan:
- Apply Hohmann dv0 from multiple phasings
- Propagate, find best perilune
- Apply solve_arrival_eccentric at perilune (no dv1 mid-burn = 2-impulse)
- Record mass

Per-pair cost: ~8 Hohmann seeds × (propagate + solve_arrival) ≈ 1 sec wall.
For 11k feasibles / 8 workers = 1400 sec ≈ 23 min.

Output: tier1_light_results.json — used by Hungarian rebank to identify
gain potential.
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
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3
ISP_G0 = 311.0 * 9.80665
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
    """Light eval: try 8 Hohmann seeds, return best mass via 2-impulse."""
    idE, idL = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    t_max_nd = 25.0 * 86400.0 / T

    best = None
    for raan_e in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        for ea_dep in (0.0, math.pi):
            pv0 = earth_orbit_state(aE, eE, iE, raan_e, 0.0, ea_dep)
            dv0 = _hohmann_dv0_synbasis(pv0)
            dv0_mag = math.sqrt(dv0[0] ** 2 + dv0[1] ** 2 + dv0[2] ** 2) * V
            for t0 in (0.0, math.pi):
                try:
                    t_peri, state, r_min, imp = track_to_perilune(
                        pv0, t0, dv0, t_max_nd)
                except Exception:
                    continue
                if imp:
                    continue
                # Quick arrival evaluation at perilune state
                pv_arr = [list(state[:3]), list(state[3:6])]
                res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
                if res is None:
                    continue
                dv2 = res[0]
                if not np.all(np.isfinite(dv2)):
                    continue
                dv2_mag = math.sqrt(dv2[0] ** 2 + dv2[1] ** 2 + dv2[2] ** 2) * V
                dv_total = dv0_mag + dv2_mag
                if dv_total > 12000:
                    continue
                mass = math.exp(-dv_total / ISP_G0) * 5000.0 - 500.0
                if mass < 0:
                    continue
                # Build row for verification (T2=0 for 2-impulse)
                T1 = t_peri
                row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
                        dv0[0], dv0[1], dv0[2],
                        0.0, 0.0, 0.0,
                        float(dv2[0]), float(dv2[1]), float(dv2[2]),
                        T1, 0.0]
                # Verify via UDP fitness
                chr_p = list(row)
                pad = (udp.dim - len(chr_p)) // 21
                for _ in range(pad):
                    chr_p.extend([-1.0] + [0.0] * 20)
                f = udp.fitness(chr_p)[0]
                if f >= 0:
                    continue
                actual_mass = -f
                if best is None or actual_mass > best[0]:
                    best = (actual_mass, row, dv_total)
    return idE, idL, best


def main(n_workers=8,
          feasibility_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/feasibility_matrix.json",
          out_path="/home/julian/Projects/esa_spoc_26_3/runs/ch1/tier1_light_results.json"):
    udp = LtlTrajectory(ROOT)
    fmat = json.load(open(feasibility_path))
    feasibles = [k for k, v in fmat.items() if v[2]]
    print(f"Loaded {len(feasibles)} feasibles from matrix", flush=True)

    # Filter to UNTESTED
    tested = set()
    rd = Path("/home/julian/Projects/esa_spoc_26_3/runs/ch1")
    for f in rd.glob("*results*.json"):
        try:
            d = json.load(open(f))
            for k in d.keys():
                tested.add(k)
        except Exception:
            pass
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        for i in range(0, len(dv), 21):
            if dv[i] >= 0:
                tested.add(f"{int(dv[i])},{int(dv[i + 1])}")
    new_keys = [k for k in feasibles if k not in tested]
    print(f"Already tested: {len(tested)}, NEW to evaluate: {len(new_keys)}",
           flush=True)

    pairs = [(int(k.split(',')[0]), int(k.split(',')[1])) for k in new_keys]
    print(f"Est wall: ~{len(pairs) * 1.0 / n_workers / 60:.0f} min", flush=True)

    t_start = time.time()
    results = {}
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_task, pairs, chunksize=20):
            n_done += 1
            if best is not None and best[0] > 50:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 500 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                top_m = sorted([v[0] for v in results.values()],
                                reverse=True)[:5]
                top_str = ",".join(f"{m:.0f}" for m in top_m)
                print(f"  [{n_done:5d}/{len(pairs)}] valid={n_valid} "
                      f"top5=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
            if n_done % 1000 == 0:
                serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                                 for k, v in results.items()}
                Path(out_path).write_text(json.dumps(serializable))

    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    Path(out_path).write_text(json.dumps(serializable))
    print(f"\nTier 1 done in {time.time()-t_start:.0f}s: "
          f"{n_valid}/{n_done} valid", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=nw)
