"""Test long-TOF transfers on currently-worst pairs.

Hypothesis: 50-100 day TOFs activate Sun-assisted plane change in BCP,
unlocking dramatically higher mass for LEO+inclined-Moon pairs.

For each bottom-mass transfer in the bank, try:
- TOF in {20, 40, 60, 80, 100} days
- t0 in {0, π/2, π, 3π/2} (Sun phase)
- ea_dep, ea_arr sweeps

If any trajectory beats the current mass, report.
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
import pykep as pk

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


def try_long_tof_transfer(idE, idL, tof_d, t0_val, ea_dep, ea_arr):
    """Lambert seed + 3-D DC at long TOF + specified t0."""
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
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
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
    return mass, row, dv_ms


def _solve_long(args):
    idE, idL, current_mass = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    for tof_d in (15, 25, 40, 60, 80):
        for t0_val in np.linspace(0, 2 * np.pi, 4, endpoint=False):
            for ea_dep in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                for ea_arr in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                    res = try_long_tof_transfer(idE, idL, tof_d, t0_val,
                                                   ea_dep, ea_arr)
                    if res is not None and res[0] > current_mass:
                        if best is None or res[0] > best[0]:
                            best = (res[0], res[1], res[2], tof_d, t0_val)
    return idE, idL, current_mass, best


def main(n_workers=8, bottom_n=30):
    udp = LtlTrajectory(ROOT)
    bank = json.load(open("solutions/upload/trajectory.json"))
    dv_chr = bank[0]["decisionVector"]

    # Find bottom-mass transfers
    rows = []
    for i in range(0, len(dv_chr), 21):
        if dv_chr[i] < 0:
            continue
        row = dv_chr[i:i + 21]
        idE = int(row[0])
        idL = int(row[1])
        mass = evaluate_row(row, udp)
        rows.append((mass, idE, idL, i // 21))
    rows.sort()  # low to high

    bottom = rows[:bottom_n]
    print(f"Testing long TOF on bottom {len(bottom)} transfers:", flush=True)
    for m, idE, idL, idx in bottom:
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        print(f"  [{idx:3d}] ({idE:3d},{idL:3d}): mass={m:.0f} "
              f"iE={iE:.2f} iL={iL:.2f}", flush=True)

    print(f"\nLaunching parallel long-TOF search...", flush=True)
    t_start = time.time()
    pairs = [(idE, idL, m) for m, idE, idL, _ in bottom]
    n_improved = 0
    total_gain = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, current_mass, best in p.imap_unordered(
                _solve_long, pairs, chunksize=1):
            if best is not None:
                mass, row, dv_ms, tof_d, t0_val = best
                gain = mass - current_mass
                print(f"  ({idE:3d},{idL:3d}) {current_mass:.0f} → {mass:.0f} kg "
                      f"(+{gain:.0f}) tof={tof_d}d t0={t0_val:.2f}",
                      flush=True)
                n_improved += 1
                total_gain += gain
            else:
                print(f"  ({idE:3d},{idL:3d}) no long-TOF improvement",
                      flush=True)
    wall = time.time() - t_start
    print(f"\nLong-TOF test done in {wall:.0f}s: {n_improved}/{len(bottom)} improved, +{total_gain:.0f} kg",
          flush=True)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(n_workers=nw, bottom_n=n)
