"""E-567 — the CORRECT impulsive-geometry GO/NO-GO (replaces null E-566).

E-566 failed because it rebuilt a fresh crude seed+DC harness that could not
construct a single BCP-valid transfer (0/560, even on banked pairs). This
script instead reuses the PROVEN solver primitive `try_transfer` from
ch1_traj_proper_v2 (the one that already banks GEO pairs at ~96% of bound) and
changes ONLY ONE thing: it sweeps the Earth-orbit RAAN (departure node) instead
of fixing it at 0.

Hypothesis (the geometric lever): the official validator checks only (a,e,i) at
both ends, so RAAN is free. Letting the departure node rotate should let the
plane align with the Earth->Moon encounter, cutting the plane-change cost — IF
that cost is real and BCP-realizable. The LEO->Moon pairs are where the claimed
headroom lives (corrected patched-conic bounds): (118,171) banked 949 / bound
1266 (+33%); (0,150) bound 1086 unbanked.

TEST: for each pair, baseline = best mass at raan_E=0 (reproduces banked-ish),
then sweep raan_E. GO if some raan_E meaningfully beats the raan_E=0 baseline
AND approaches the bound. NO-GO (real this time) if mass plateaus at the
raan_E=0 value -> free RAAN gives nothing under BCP -> 371k ceiling stands.

Incremental: prints every new best + a heartbeat every 60 trials. Per-pair wall
budget so it can never go blind. Read-only w.r.t. deliverables.

Run: PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
        python -u scripts/ch1_e567_raan_lever.py
"""
from __future__ import annotations

import time

import numpy as np

from esa_spoc_26.ch1_trajectory import (
    T, LtlTrajectory, earth_orbit_state, moon_orbit_state,
)
from esa_spoc_26.ch1_traj_proper_v2 import try_transfer

BASE = "reference/SpOC4/Challenge 1 Luna Tomato Logistics/"

# (idE, idL, banked, corrected_bound, label)
PAIRS = [
    (118, 171, 949.4, 1266.0, "LEO i25 -> hi-e Moon [E-036]"),
    (0, 150, 0.0, 1086.0, "LEO i0  -> hi-e Moon [unbanked]"),
]

TOF_GRID = (5.0, 6.0, 8.0)
N_EA_DEP = 6
N_EA_ARR = 6
N_RAAN_E = 8          # the lever: 8 departure-node orientations
PAIR_BUDGET_S = 540.0  # wall cap/pair so we never go blind


def scan_pair(udp, idE, idL, raan_E):
    """Best valid mass over (tof, ea_dep, ea_arr) at a FIXED departure RAAN."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    for tof_d in TOF_GRID:
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, N_EA_DEP, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, raan_E, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, N_EA_ARR, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                res = try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                   aL, eL, iL, tof, dc_mode="6d",
                                   idE=idE, idL=idL)
                if res is None:
                    continue
                mass = res[0]
                if best is None or mass > best[0]:
                    best = (mass, res[2], tof_d, ea_dep, ea_arr)
    return best


def main():
    udp = LtlTrajectory(BASE)
    print("=" * 74, flush=True)
    print("E-567 RAAN lever — proven try_transfer + departure-node sweep",
          flush=True)
    print("=" * 74, flush=True)
    raanE_grid = np.linspace(0, 2 * np.pi, N_RAAN_E, endpoint=False)
    summary = []
    for idE, idL, banked, bound, label in PAIRS:
        print(f"\n### {label}  idE={idE} idL={idL}  "
              f"banked={banked:.0f} bound={bound:.0f}", flush=True)
        t0 = time.time()
        baseline = None
        best_overall = None
        for k, raan_E in enumerate(raanE_grid):
            if time.time() - t0 > PAIR_BUDGET_S:
                print(f"  [budget {PAIR_BUDGET_S:.0f}s hit after "
                      f"{k}/{N_RAAN_E} RAANs]", flush=True)
                break
            b = scan_pair(udp, idE, idL, raan_E)
            if b is None:
                print(f"  raan_E={raan_E:.3f} ({k+1}/{N_RAAN_E}): "
                      f"no valid", flush=True)
                continue
            if k == 0:
                baseline = b[0]
            mark = ""
            if best_overall is None or b[0] > best_overall[0]:
                best_overall = (b[0], raan_E, b[1], b[2], b[3], b[4])
                mark = " <-- BEST"
            print(f"  raan_E={raan_E:.3f} ({k+1}/{N_RAAN_E}): "
                  f"mass={b[0]:.1f}kg dv={b[1]:.0f} tof={b[2]:.0f}d{mark}",
                  flush=True)
        if best_overall is None:
            print("  PAIR: no valid candidate at any RAAN", flush=True)
            summary.append((label, idE, idL, banked, bound, None, None))
            continue
        gain = best_overall[0] - (baseline if baseline else 0.0)
        pct = 100 * best_overall[0] / bound
        print(f"  PAIR RESULT: baseline(raan0)={baseline:.1f} -> "
              f"best={best_overall[0]:.1f}kg @raan_E={best_overall[1]:.3f} "
              f"(RAAN gain {gain:+.1f}kg); {pct:.0f}% of bound; "
              f"vs banked {best_overall[0]-banked:+.0f}", flush=True)
        summary.append((label, idE, idL, banked, bound,
                        best_overall[0], baseline))

    print("\n" + "=" * 74, flush=True)
    print("VERDICT", flush=True)
    print("=" * 74, flush=True)
    real_lever = []
    for label, idE, idL, banked, bound, best, base in summary:
        if best is None:
            print(f"  ({idE},{idL}) {label}: NO VALID", flush=True)
            continue
        gain = best - (base if base else 0.0)
        pct = 100 * best / bound
        lever = gain > 20.0 and best > banked  # >20kg RAAN gain AND beats bank
        real_lever.append(lever)
        print(f"  ({idE},{idL}) best={best:.0f} ({pct:.0f}% bound) "
              f"RAAN-gain={gain:+.0f} vs-bank={best-banked:+.0f} "
              f"-> lever={'YES' if lever else 'no'}", flush=True)
    if real_lever and any(real_lever):
        print("\n  >>> GO signal: free-RAAN beats raan=0 baseline on LEO "
              "pair(s) -> the geometric lever IS BCP-realizable; "
              "design full LEO-pair re-solve.", flush=True)
    else:
        print("\n  >>> NO-GO (real): free-RAAN gives no gain over raan=0 "
              "under BCP -> impulsive ceiling stands, WSB stays top.",
              flush=True)


if __name__ == "__main__":
    main()
