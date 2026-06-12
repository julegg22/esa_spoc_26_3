"""E-576 Phase A pre-step: recover the bank's actual departure/arrival
orbital elements for the high-incl known-feasible pairs E252, E100 (and the
low-incl controls E0/E69/E54). The bank row stores pv0=[r[4:7],r[7:10]] in
synodic BCP coords; state2earth maps that to (a,e,i,raan,argp,ea). If raan or
argp is NONZERO for the high-incl pairs, the bank used the free DoF the lead
posits and Phase A's raan=argp=0 baseline CANNOT reproduce them.

Also recovers the arrival side: re-propagate the bank's DVs/Ts and run
state2moon to read the realized arrival elements (incl raan/argp).
Read-only.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pykep as pk

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")

from esa_spoc_26.ch1_trajectory import (  # noqa: E402
    L, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON, V,
    LtlTrajectory, propagate, state2earth, state2moon,
)

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def earth_full_elements(posvel):
    """Full 6 elements (a,e,i,raan,argp,ea) on the Earth side."""
    [x, y, z], [vx, vy, vz] = posvel
    vx_EF = (vx - y) * V
    vy_EF = (vy + x) * V
    vz_EF = vz * V
    vy_EF = vy_EF - (-CR3BP_MU_EARTH_MOON) * V
    x_EF = (x + CR3BP_MU_EARTH_MOON) * L
    y_EF = y * L
    z_EF = z * L
    return pk.ic2par([x_EF, y_EF, z_EF], [vx_EF, vy_EF, vz_EF], MU_EARTH)


def moon_full_elements(posvel):
    [x, y, z], [vx, vy, vz] = posvel
    vx_MF = (vx - y) * V
    vy_MF = (vy + x) * V
    vz_MF = vz * V
    vy_MF = vy_MF - (1.0 - CR3BP_MU_EARTH_MOON) * V
    x_MF = (x - 1 + CR3BP_MU_EARTH_MOON) * L
    y_MF = y * L
    z_MF = z * L
    return pk.ic2par([x_MF, y_MF, z_MF], [vx_MF, vy_MF, vz_MF], MU_MOON)


def main():
    udp = LtlTrajectory(DD)
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0][
        "decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    # Build idE -> row map for used rows
    by_idE = {int(r[0]): r for r in rows if r[0] >= 0}
    targets = {
        "E0": 0, "E69": 69, "E54": 54, "E252": 252, "E100": 100,
    }
    print("[E-576] Bank element recovery (departure & arrival full elements)",
          flush=True)
    print("=" * 78, flush=True)
    for name, idE in targets.items():
        if idE not in by_idE:
            print(f"{name}: idE={idE} NOT a used row in bank", flush=True)
            continue
        r = by_idE[idE]
        idL = int(r[1])
        pv0 = [list(r[4:7]), list(r[7:10])]
        DVs = [list(r[10:13]), list(r[13:16]), list(r[16:19])]
        Ts = [float(r[19]), float(r[20])]
        # departure elements
        el_dep = earth_full_elements(pv0)
        a, e, i, raan, argp, ea = el_dep
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        mass = -udp.fitness(list(r))[0]
        # arrival elements: re-propagate
        pv1 = propagate(pv0, 0.0, DVs, Ts)
        if len(pv1) == 0:
            arr_str = "ARRIVAL PROPAGATE FAILED"
        else:
            ael = moon_full_elements(pv1)
            arr_str = (f"arr raan={np.degrees(ael[3]):.2f} "
                       f"argp={np.degrees(ael[4]):.2f} i={np.degrees(ael[2]):.2f}")
        dv0n = np.linalg.norm(DVs[0]) * V
        dv1n = np.linalg.norm(DVs[1]) * V
        dv2n = np.linalg.norm(DVs[2]) * V
        T1d = Ts[0] * 3.7567696752e5 * pk.SEC2DAY
        T2d = Ts[1] * 3.7567696752e5 * pk.SEC2DAY
        split = T1d / (T1d + T2d) if (T1d + T2d) > 0 else 1.0
        print(f"{name} idE={idE} idL={idL} mass={mass:.1f}kg", flush=True)
        print(f"   DEP recovered: a={a/1e3:.1f}km e={e:.3e} "
              f"i={np.degrees(i):.3f}deg raan={np.degrees(raan):.3f}deg "
              f"argp={np.degrees(argp):.3f}deg ea={np.degrees(ea):.2f}deg",
              flush=True)
        print(f"   DEP catalog  : a={aE/1e3:.1f}km e={eE:.3e} "
              f"i={np.degrees(iE):.3f}deg  (target i for arrival "
              f"iL={np.degrees(iL):.3f})", flush=True)
        print(f"   {arr_str}", flush=True)
        print(f"   dv0={dv0n:.1f} dv1={dv1n:.1f} dv2={dv2n:.1f} m/s | "
              f"T1={T1d:.3f}d T2={T2d:.3f}d split={split:.3f} "
              f"tof={T1d+T2d:.3f}d", flush=True)
        # KEY VERDICT for this pair:
        raan_deg = abs((np.degrees(raan) + 180) % 360 - 180)
        argp_deg = abs((np.degrees(argp) + 180) % 360 - 180)
        flag = "RAAN/ARGP ~0 (pinned)" if (raan_deg < 0.5 and argp_deg < 0.5) \
            else f"NONZERO raan={raan_deg:.2f} argp={argp_deg:.2f} <<<"
        print(f"   => DEP DoF: {flag}", flush=True)
        print("-" * 78, flush=True)


if __name__ == "__main__":
    main()
