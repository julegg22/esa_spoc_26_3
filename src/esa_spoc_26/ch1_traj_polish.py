"""Ch1 Trajectory — continuous polish of a working transfer row.

The 14.82 kg (idE=0, idL=0) row uses dv=6933 m/s. The Hohmann
minimum is ~3900 m/s = 893 kg mass. The 3 km/s "extra" comes from:
- Suboptimal apoapsis-Moon alignment
- LOI angle/timing mismatch
- Plane-change leftover

Polish via scipy.optimize.minimize on the 14 continuous vars:
(raan, argp, ea, t0, dv0[3], dv1[3], dv2[3], T1, T2)

Use the UDP's actual fitness as the objective. The polisher walks
the basin around the working point to find lower-dv configurations.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch1_trajectory import LtlTrajectory, earth_orbit_state


def chromosome_from_params(udp, idE, idL, idD, raan, argp, ea, t0,
                              dv0, dv1, dv2, T1, T2):
    """Build a 21-var row from parameters."""
    aE, eE, iE = udp.earth_data[idE]
    pv0 = earth_orbit_state(aE, eE, iE, raan, argp, ea)
    return [idE, idL, idD, t0, *pv0[0], *pv0[1],
             *dv0, *dv1, *dv2, T1, T2]


def fitness_single_row(udp, row):
    """Pad row to 8400-dim chromosome and return udp.fitness."""
    chrom = list(row)
    pad_count = (udp.dim - len(chrom)) // 21
    for _ in range(pad_count):
        chrom.extend([-1] + [0.0] * 20)
    return udp.fitness(chrom)[0]


def polish_one(udp, idE, idL, idD, raan0, argp0, ea0, t0_0,
                 dv0_0, dv1_0, dv2_0, T1_0, T2_0, n_starts=5,
                 verbose=False):
    """Polish a row's 14 continuous params via scipy minimize."""
    best_fit = None
    best_x = None
    # Initial seed: the working row
    x0 = np.array([raan0, argp0, ea0, t0_0,
                    *dv0_0, *dv1_0, *dv2_0, T1_0, T2_0])

    def objective(x):
        raan, argp, ea, t0 = x[0], x[1], x[2], x[3]
        dv0 = x[4:7].tolist()
        dv1 = x[7:10].tolist()
        dv2 = x[10:13].tolist()
        T1 = float(x[13])
        T2 = float(x[14])
        row = chromosome_from_params(udp, idE, idL, idD,
                                          float(raan), float(argp),
                                          float(ea), float(t0),
                                          dv0, dv1, dv2, T1, T2)
        f = fitness_single_row(udp, row)
        # Return negated mass (we maximize mass = -fitness)
        return f  # We minimize fitness (which is -mass)

    # Multi-start
    for s in range(n_starts):
        if s == 0:
            x_init = x0
        else:
            # Perturb
            rng = np.random.default_rng(s * 31 + 7)
            scale = np.array([0.1, 0.1, 0.1, 0.5,   # raan/argp/ea/t0
                               0.01, 0.01, 0.01,    # dv0
                               0.001, 0.001, 0.001,  # dv1
                               0.01, 0.01, 0.01,    # dv2
                               0.05, 0.001])         # T1, T2
            x_init = x0 + rng.normal(0, scale, size=15)
        try:
            res = minimize(objective, x_init, method="Nelder-Mead",
                              options={"maxiter": 300, "xatol": 1e-6,
                                        "fatol": 1e-6, "disp": False})
        except Exception as e:
            if verbose:
                print(f"  start {s}: minimize error {e}")
            continue
        if res.fun < 0 and (best_fit is None or res.fun < best_fit):
            best_fit = res.fun
            best_x = res.x
            if verbose:
                print(f"  start {s}: fitness={res.fun:.2f}, "
                      f"mass={-res.fun:.1f} kg", flush=True)
    return best_x, best_fit


def main():
    """Polish the existing 14.82 kg (idE=0, idL=0) row."""
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    # Load existing banked row
    p = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    d = json.load(open(p))
    chrom = d[0]["decisionVector"]
    # First transfer = first 21 vars
    row0 = chrom[:21]
    idE, idL, idD = int(row0[0]), int(row0[1]), int(row0[2])
    t0_0 = row0[3]
    # Decompose pv0 - extract raan, argp, ea from state via state2earth
    # Actually easier: just keep pv0 components and parameterize new pv0
    # We'll use raan_init = 0 (since earlier we found raan=π/2 worked)
    # But the saved row was at raan=π/2 from the targeted sweep
    # Actually let's just back out using state2earth: but state2earth gives (a, e, i) only
    # Use approximate raan, argp, ea by fitting (overkill — just keep variables free)
    # For now, polish around the saved row, freeing raan, argp, ea as zero
    # (the polisher will find them)
    # Simpler: re-derive a working row via solve_transfer_direct and polish that.
    from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct
    print("Re-deriving working (0, 0) row via solve_transfer_direct...", flush=True)
    # The 14.82 kg was at raan=π/2 per the sweep
    res = solve_transfer_direct(udp, 0, 0, n_phase=16, t0=0.0, raan=np.pi/2, argp=0.0)
    if res[0] is None:
        # Fall back to raan=0
        res = solve_transfer_direct(udp, 0, 0, n_phase=16, t0=0.0, raan=0.0, argp=0.0)
    row0, mass0, dv_ms_0, dt_d_0 = res[0], res[1], res[2], res[3]
    print(f"Working seed: mass={mass0:.2f} kg, dv={dv_ms_0:.0f} m/s, "
          f"tof={dt_d_0:.1f}d", flush=True)
    # Extract params from row0
    idE = int(row0[0])
    idL = int(row0[1])
    idD = int(row0[2])
    t0 = float(row0[3])
    pv0_pos = list(row0[4:7])
    pv0_vel = list(row0[7:10])
    dv0 = list(row0[10:13])
    dv1 = list(row0[13:16])
    dv2 = list(row0[16:19])
    T1 = float(row0[19])
    T2 = float(row0[20])
    print(f"  Initial dv0={[f'{x:.4f}' for x in dv0]}, "
          f"dv2={[f'{x:.4f}' for x in dv2]}, T1={T1:.4f}", flush=True)

    # Polish: vary (t0, dv0, dv1, dv2, T1, T2) keeping pv0 fixed (so orbit identity is preserved)
    def objective(x):
        t0_, dv0_x, dv0_y, dv0_z, dv1_x, dv1_y, dv1_z, dv2_x, dv2_y, dv2_z, T1_, T2_ = x
        row = [idE, idL, idD, float(t0_), *pv0_pos, *pv0_vel,
               float(dv0_x), float(dv0_y), float(dv0_z),
               float(dv1_x), float(dv1_y), float(dv1_z),
               float(dv2_x), float(dv2_y), float(dv2_z),
               float(T1_), float(T2_)]
        chrom = list(row) + [-1] + [0.0] * 20
        # Pad
        n_pad = (udp.dim - len(chrom)) // 21
        for _ in range(n_pad - 1):  # -1 since we already added 1 dummy
            chrom.extend([-1] + [0.0] * 20)
        return udp.fitness(chrom)[0]

    x0 = np.array([t0, *dv0, *dv1, *dv2, T1, T2])
    print(f"\nInitial fitness: {objective(x0):.4f}", flush=True)
    print(f"Polishing via Nelder-Mead...", flush=True)
    t_start = time.time()
    res = minimize(objective, x0, method="Nelder-Mead",
                      options={"maxiter": 2000, "xatol": 1e-8,
                                "fatol": 1e-4, "disp": True,
                                "adaptive": True})
    wall = time.time() - t_start
    print(f"\nPolish done in {wall:.0f}s: fitness={res.fun:.4f}, "
          f"mass={-res.fun:.2f} kg", flush=True)
    if res.fun < -mass0 - 0.5:
        # Build new chromosome
        t0_, *dvs, T1_, T2_ = res.x
        new_row = [idE, idL, idD, float(t0_), *pv0_pos, *pv0_vel,
                    *dvs[:9], float(T1_), float(T2_)]
        new_chrom = list(new_row)
        n_pad = (udp.dim - len(new_chrom)) // 21
        for _ in range(n_pad):
            new_chrom.extend([-1] + [0.0] * 20)
        f = udp.fitness(new_chrom)
        print(f"Final UDP check: fitness={f[0]:.4f}, mass={-f[0]:.2f}",
              flush=True)
        if f[0] < -mass0:
            p.write_text(json.dumps([{
                "decisionVector": [float(v) for v in new_chrom],
                "problem": "trajectory",
                "challenge": "spoc-4-luna-tomato-logistics",
            }]))
            print(f"BANKED (improved {mass0:.1f} → {-f[0]:.1f} kg)",
                  flush=True)


if __name__ == "__main__":
    main()
