"""E-048 probe — Ch1 trajectory: does sweeping the FREE RAAN/argp DoF unlock
the 99 unfilled high-inclination slots?

Confirmed facts: the official validator `_match_orbit` checks ONLY (a,e,i);
RAAN and argp of both the Earth departure orbit and the Moon arrival orbit
are FREE. Every solver (ch1_traj_proper_v2.scan_and_polish,
ch1_multi_restart_6d) hardcodes raan=argp=0. The 99 unfilled bank slots are
systematically the high-incl Earth orbits (unused median 74.3 deg vs used
24 deg). Hypothesis: pinning RAAN/argp=0 strands high-incl pairs; sweeping
the relative plane orientation makes some feasible.

This is a CONFIRMATION probe only — read-only, writes nothing to solutions.
For a handful of currently-FAILING high-incl (Earth->Moon) pairs it compares
baseline (raan=argp=0) vs an orientation sweep, reusing the EXACT solver
(try_transfer, 6-D DC). If sweep flips infeasible->feasible on even one
pair, the lead is confirmed and warrants the full re-solve campaign.
"""
import itertools
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch1_trajectory import T, earth_orbit_state, moon_orbit_state  # noqa: E402
from esa_spoc_26.ch1_traj_proper_v2 import try_transfer  # noqa: E402

DD = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


class UDP:
    def __init__(self):
        from esa_spoc_26.ch1_trajectory import LtlTrajectory
        self.u = LtlTrajectory(DD)
        self.earth_data = self.u.earth_data
        self.moon_data = self.u.moon_data
        self.dim = self.u.dim

    def fitness(self, x):
        return self.u.fitness(x)


def best_mass(udp, idE, idL, earth_orients, moon_orients, tofs, n_ea):
    """Best feasible mass over the given orientation/ea/tof grid, or None."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    eas = np.linspace(0, 2 * np.pi, n_ea, endpoint=False)
    best = None
    n_feas = 0
    for tof_d in tofs:
        tof = tof_d * 86400.0 / T
        for (rae, age) in earth_orients:
            for ea_d in eas:
                pv0 = earth_orbit_state(aE, eE, iE, rae, age, ea_d)
                for (ral, agl) in moon_orients:
                    for ea_a in eas:
                        pv_tgt = moon_orbit_state(aL, eL, iL, ral, agl, ea_a)
                        res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                           aL, eL, iL, tof, dc_mode="6d",
                                           idE=idE, idL=idL)
                        if res is None:
                            continue
                        n_feas += 1
                        m = res[0]
                        if best is None or m > best:
                            best = m
    return best, n_feas


def main():
    udp = UDP()
    earth, moon = udp.earth_data, udp.moon_data
    import json
    b = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    rows = np.array(b).reshape(-1, 21)
    usedE = set(int(r[0]) for r in rows if r[0] >= 0)
    usedL = set(int(r[1]) for r in rows if r[0] >= 0)
    unusedE = [k for k in range(len(earth)) if k not in usedE]
    unusedL = [k for k in range(len(moon)) if k not in usedL]
    # highest-inclination unused Earth orbits = the hard, stranded ones
    hiE = sorted(unusedE, key=lambda k: -earth[k, 2])[:4]
    # pair each with the unused Moon orbits of nearest inclination (a few)
    print(f"[probe] {len(unusedE)} unused Earth, {len(unusedL)} unused Moon. "
          f"testing hi-incl Earth {hiE}", flush=True)

    BASE_ORIENT = [(0.0, 0.0)]
    SWEEP_E = list(itertools.product(
        np.linspace(0, 2 * np.pi, 6, endpoint=False),
        np.linspace(0, 2 * np.pi, 2, endpoint=False)))   # 12 earth orientations
    SWEEP_L = list(itertools.product(
        np.linspace(0, 2 * np.pi, 3, endpoint=False), [0.0]))  # 3 moon orientations
    TOFS = (8.0, 12.0, 18.0)
    N_EA = 3

    any_unlocked = False
    for idE in hiE:
        iE_deg = np.degrees(earth[idE, 2])
        # 3 unused moons closest in inclination
        cand = sorted(unusedL, key=lambda k: abs(moon[k, 2] - earth[idE, 2]))[:3]
        for idL in cand:
            iL_deg = np.degrees(moon[idL, 2])
            t0 = time.time()
            base, nb = best_mass(udp, idE, idL, BASE_ORIENT, BASE_ORIENT,
                                 TOFS, N_EA)
            swp, ns = best_mass(udp, idE, idL, SWEEP_E, SWEEP_L, TOFS, N_EA)
            tag = ""
            if base is None and swp is not None:
                tag = "  <<< UNLOCKED (baseline FAIL, sweep OK)"
                any_unlocked = True
            elif base is not None and swp is not None and swp > base + 1.0:
                tag = f"  (sweep +{swp-base:.0f}kg)"
            print(f"E{idE}(i={iE_deg:.0f}) L{idL}(i={iL_deg:.0f}): "
                  f"base={'FAIL' if base is None else f'{base:.0f}kg'}(nf={nb}) "
                  f"sweep={'FAIL' if swp is None else f'{swp:.0f}kg'}(nf={ns}) "
                  f"[{time.time()-t0:.0f}s]{tag}", flush=True)

    print(f"\n[VERDICT] {'CONFIRMED — RAAN/argp sweep unlocks stranded slots' if any_unlocked else 'no unlock on tested pairs (try split sweep / more orientations)'}",
          flush=True)


if __name__ == "__main__":
    main()
