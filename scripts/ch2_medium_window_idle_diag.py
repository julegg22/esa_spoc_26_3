"""E-759 — Ch2 medium narrow-window / idle diagnostic (post-challenge rank-1 investigation).

Tests the HRI rank-1 hint (they exploit narrow phasing-window basins) against our banked medium
tour. Measures:
  (1) makespan decomposition: transfer-time (sum tofs) vs idle/wait time (sum of gaps between
      arrival of leg i and departure of leg i+1). Idle is the direct target for window-alignment.
  (2) per-leg, for legs with idle>eps: scan Delta-v vs t_dep across the idle gap [arr_prev, t_dep_bank]
      at fine resolution (fixed banked tof), to ask: was there a CHEAP (<=100) departure instant
      EARLIER in the gap that we failed to use? If yes -> idle is removable by better (continuous-time)
      retiming = a search/resolution miss (buildable lever). If the whole gap is Delta-v-hostile ->
      idle is phasing-forced (needs reorder, not retime).
  (3) window narrowness: at the banked departure, measure the width of the cheap-feasible t_dep band
      (how many days wide is the basin we're sitting in) -> tests "sub-grid narrow" (our 0.1d grid blind).

Diagnostic only; banks nothing. Emits a decomposition + per-leg removable-idle upper bound.
Usage: python ch2_medium_window_idle_diag.py [n_idle_legs=25] [step=0.02]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "src")
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/medium.kttsp")
BANK = "solutions/upload/medium.json"


def band_width(kt, i, j, t_center, tof, step=0.01, span=1.0):
    """Width (days) of the contiguous cheap (<=100) t_dep band containing t_center, fixed tof."""
    dv_c = kt.compute_transfer(i, j, float(t_center), float(tof))
    if dv_c > kt.dv_thr + 1e-6:
        return 0.0, dv_c
    lo = t_center
    while lo - step >= 0.0 and kt.compute_transfer(i, j, float(lo - step), float(tof)) <= kt.dv_thr:
        lo -= step
        if t_center - lo > span:
            break
    hi = t_center
    while kt.compute_transfer(i, j, float(hi + step), float(tof)) <= kt.dv_thr:
        hi += step
        if hi - t_center > span:
            break
    return hi - lo, dv_c


def main():
    n_idle_legs = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.02
    kt = KTTSP(INST)
    n = kt.n
    x = json.load(open(BANK))[0]["decisionVector"]
    times = np.array(x[:n - 1], float)
    tofs = np.array(x[n - 1:2 * n - 2], float)
    order = [round(v) for v in x[2 * n - 2:]]
    f = kt.fitness(x)
    print(f"[E-759] medium bank makespan={f[0]:.4f}d feasible={kt.is_feasible(f)} "
          f"(perm_c={f[1]} dv_cnt={f[2]} time_cnt={f[3]} exc={f[4]}) n={n}", flush=True)

    arr = times + tofs                       # arrival time of each leg
    idle = np.zeros(n - 1)
    idle[0] = times[0]                        # wait before the very first departure
    idle[1:] = times[1:] - arr[:-1]           # wait at node before departing leg i
    total_tof = float(tofs.sum())
    total_idle = float(idle.sum())
    print(f"[E-759] makespan {f[0]:.3f}d = transfer {total_tof:.3f}d + idle {total_idle:.3f}d "
          f"(first-dep wait {idle[0]:.3f}d)", flush=True)
    print(f"[E-759] idle: legs with idle>0.05d = {(idle > 0.05).sum()}/{n-1}; "
          f"top idle legs (leg_idx, idle_d): "
          f"{[(int(k), round(float(idle[k]),3)) for k in np.argsort(-idle)[:8]]}", flush=True)

    # per-leg dv classification
    t0 = time.time()
    dvs = np.array([kt.compute_transfer(order[i], order[i + 1], float(times[i]), float(tofs[i]))
                    for i in range(n - 1)])
    print(f"[E-759] leg Delta-v: cheap(<=100)={(dvs <= kt.dv_thr + 1e-6).sum()} "
          f"exc(100-600)={((dvs > kt.dv_thr) & (dvs <= kt.dv_exc + 1e-6)).sum()} "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # (2) removable-idle probe on the top idle legs + (3) band width
    idle_legs = [k for k in np.argsort(-idle) if idle[k] > 0.05][:n_idle_legs]
    removable = 0.0
    narrow_widths = []
    print(f"[E-759] probing {len(idle_legs)} highest-idle legs (step={step}d):", flush=True)
    for k in idle_legs:
        i, j = order[k], order[k + 1]
        tof = float(tofs[k])
        gap_lo = float(arr[k - 1]) if k >= 1 else 0.0
        gap_hi = float(times[k])
        # scan the idle gap for an EARLIER cheap departure (fixed banked tof)
        tds = np.arange(gap_lo, gap_hi + 1e-9, step)
        if len(tds) < 2:
            continue
        cheap_ts = [td for td in tds
                    if kt.compute_transfer(i, j, float(td), tof) <= kt.dv_thr + 1e-6]
        earliest_cheap = min(cheap_ts) if cheap_ts else None
        # width of the band at the banked departure
        w, dvc = band_width(kt, i, j, gap_hi, tof, step=max(step / 4, 0.005))
        narrow_widths.append(w)
        if earliest_cheap is not None and earliest_cheap < gap_hi - step:
            saved = gap_hi - earliest_cheap
            removable += saved
            print(f"  leg{k:3d} ({i}->{j}) idle={idle[k]:.3f}d tof={tof:.2f} "
                  f"band_at_bank={w:.3f}d | EARLIER cheap dep at -{saved:.3f}d "
                  f"(gap [{gap_lo:.2f},{gap_hi:.2f}])", flush=True)
        else:
            print(f"  leg{k:3d} ({i}->{j}) idle={idle[k]:.3f}d tof={tof:.2f} "
                  f"band_at_bank={w:.3f}d | no earlier cheap window (phasing-forced)", flush=True)

    nw = np.array(narrow_widths) if narrow_widths else np.array([0.0])
    print(f"\n[E-759] SUMMARY", flush=True)
    print(f"  makespan {f[0]:.3f}d  transfer {total_tof:.3f}d  idle {total_idle:.3f}d", flush=True)
    print(f"  removable-idle (upper bound, top-{len(idle_legs)} legs, retime-earlier) "
          f">= {removable:.3f}d", flush=True)
    print(f"  cheap-band width at banked departure: median={np.median(nw):.3f}d "
          f"min={nw.min():.3f}d max={nw.max():.3f}d  (grid quantum 0.1d)", flush=True)
    print(f"  => if bands << 0.1d and removable-idle is large: continuous-time window-snapping "
          f"retimer is the lever. If bands wide + no earlier window: idle is order-forced (reorder).",
          flush=True)


if __name__ == "__main__":
    main()
