"""E-682: DECISIVE probe of the RE-OPENED Ch1-trajectory lever (2026-06-21 re-audit).

Re-audit verdict: the bank->leader gap (263k vs leaderboard-verified 488k, 1.85x) localizes
EXACTLY to capture into the 250 CIRCULAR (eL<0.1) Moon orbits — impulsively ~4900 m/s, but the
leader's implied mean 3255 m/s < our impulsive floor 3850 ⇒ they capture circular orbits
SUB-IMPULSIVELY. E-604 "refuted WSB" but only tested ONE pipeline (eccentric-window ballistic
capture forced onto circular targets, narrow window → failed); TRUE long-duration Sun-perturbed
capture into circular LLO was never tested. The official horizon allows 200-day transfers; our
PairUDP self-imposed T1<=30d/T2<=13d (<=43d total), EXCLUDING the low-energy regime.

THIS PROBE: take the bank's EXPENSIVE circular pairs (eL<0.1, dv>=4000), re-optimize with
EXTENDED time bounds (T1<=150d, T2<=50d) via a FRESH global search (NOT seeded from the
impulsive bank), under the same dv-minimizing PairUDP fitness (real heyoka BCP propagator).
DECISIVE: does any circular pair reach sub-4000 (toward 3255) m/s with a long-duration transfer?
  YES -> low-energy circular capture is achievable with our tools -> lever ALIVE -> build.
  NO  -> even extended-time global search can't beat ~4900 -> our tools can't realize it -> re-audit.
Also reports the dt of the best (time-discount caveat: long transfers lose to (200-dt)*c_ld cap).

Usage: python ch1_circular_capture_probe.py [n_pairs=4] [gen=200]
"""
import sys, json, time, math
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26 import ch1_pair_udp as P
from esa_spoc_26.ch1_pair_udp import PairUDP, chromosome_to_row, mass_from_row
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2.0 * math.pi
Tunit_days = 3.7567696752e5 / 86400.0   # nondim time -> days (~4.348 d)


class PairUDPExtended(PairUDP):
    """Same fitness, but time bounds extended to the low-energy regime (T1<=~150d, T2<=~50d)."""
    def get_bounds(self):
        lb = [0.0, 0.0, 0.0, 0.0, 0.05, 0.0, -5.0, -5.0, -5.0, -5.0, -5.0, -5.0]
        ub = [TWO_PI, TWO_PI, TWO_PI, TWO_PI,
              34.5, 11.5,                  # T1<=~150d, T2<=~50d (official horizon 200d)
              5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        return (lb, ub)


def impulsive_baseline(udp, br):
    """dv, dt of the bank's (impulsive) row for this pair."""
    Vunit = 3.84405e8 / 3.7567696752e5
    dv = (np.linalg.norm(br[10:13]) + np.linalg.norm(br[13:16]) + np.linalg.norm(br[16:19])) * Vunit
    return dv


def main(n_pairs=4, gen=200):
    print(f"[E-682] init: compiling heyoka BCP propagator + loading orbits ...", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    eL = udp.moon_data[:, 1]
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    Vunit = 3.84405e8 / 3.7567696752e5
    # pick EXPENSIVE circular pairs from the bank: eL<0.1 and high dv
    cands = []
    for i in range(0, len(bank), 21):
        if bank[i] < 0:
            continue
        r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
        if eL[l] >= 0.1:
            continue
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
        cands.append((dv, e, l, r))
    cands.sort(reverse=True)                     # most expensive circular captures first
    picks = cands[:n_pairs]
    print(f"[E-682] circular-capture probe: {len(cands)} circular(eL<0.1) bank pairs; testing {n_pairs} most expensive", flush=True)
    print(f"  extended bounds T1<=~150d T2<=~50d (vs impulsive <=43d); fresh global search, gen={gen}", flush=True)
    print(f"  DECISIVE: any pair reach sub-4000 m/s (toward leader 3255)?  [Tunit={Tunit_days:.3f}d]", flush=True)
    print(f"  {'pair':>12} {'eL':>5} {'imp_dv':>7}  {'ext_dv':>7} {'ext_dt':>7} {'<4000?':>7} [{'t':>4}]", flush=True)
    t0 = time.time(); wins = 0
    CHUNK = 15                                    # evolve in chunks so the descent is visible
    for imp_dv, e, l, br in picks:
        prob = pg.problem(PairUDPExtended(udp, e, l))
        algo = pg.algorithm(pg.sade(gen=CHUNK, ftol=0.0, xtol=0.0))
        algo.set_verbosity(0)
        pop = pg.population(prob, size=28, seed=1000 * e + 7 * l)
        best_dv = float("inf"); best_x = None
        done = 0
        while done < gen:
            pop = algo.evolve(pop); done += CHUNK
            if pop.champion_f[0] < best_dv:
                best_dv = float(pop.champion_f[0]); best_x = pop.champion_x
            dt_now = (best_x[4] + best_x[5]) * Tunit_days if (best_x is not None and best_dv < 1e5) else float('nan')
            print(f"    .. ({e},{l}) gen {done}/{gen} best_dv={best_dv:7.0f} (imp {imp_dv:.0f}) dt={dt_now:5.1f}d [{time.time()-t0:.0f}s]", flush=True)
        ext_dt = (best_x[4] + best_x[5]) * Tunit_days if (best_x is not None and best_dv < 1e5) else float("nan")
        hit = best_dv < 4000.0
        wins += hit
        print(f"  ({e:>4},{l:>4}) {eL[l]:5.3f} {imp_dv:7.0f}  {best_dv:7.0f} {ext_dt:6.1f}d "
              f"{'YES' if hit else 'no':>7} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-682] VERDICT: {wins}/{n_pairs} circular pairs reached sub-4000 m/s with extended-time search", flush=True)
    print(f"  >0 -> low-energy circular capture is REALIZABLE with our tools -> lever ALIVE (build, mind the dt time-discount)", flush=True)
    print(f"  0  -> extended-time global search still can't beat ~4900 -> our parametrization can't realize it -> re-audit", flush=True)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    g = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    main(n, g)
