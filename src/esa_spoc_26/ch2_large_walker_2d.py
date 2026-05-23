"""Ch2 KTTSP large — 2D time-aware walker.

For each arc (i, j) along a perm, search both td ≥ t_ready AND tof
(2D grid). The walker can WAIT before bridges to align with their
narrow feasibility windows.

Per-arc search: 30×30 (td, tof) grid → 900 Lambert evals × ~1ms.
Fast for ~1046 internal cheap arcs (only ~30 tof scans at td=t_ready
needed since SOME tof works at that exact time).
Slow for ~4 bridge arcs (need full 30×30 because td_pref may be
far from t_ready).
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_kttsp import KTTSP


def search_arc_2d(kt, i, j, t_ready, dv_cap, td_max_offset=2900.0,
                   n_td=30, n_tof=30, tof_window=30.0):
    """Search (td ≥ t_ready, tof) for cheapest dv ≤ dv_cap.

    Returns (td, tof, dv) or None if no feasible point in grid.
    """
    tof_min = max(kt.min_tof, 0.05)
    td_max = min(kt.max_time - tof_min, t_ready + td_max_offset)
    if td_max < t_ready:
        return None
    td_grid = np.linspace(t_ready, td_max, n_td)
    tof_grid = np.linspace(tof_min, tof_window, n_tof)
    best = None
    for td in td_grid:
        for tof in tof_grid:
            if td + tof > kt.max_time:
                continue
            dv = kt.compute_transfer(i, j, float(td), float(tof))
            if dv <= dv_cap:
                arrival = td + tof
                if best is None or arrival < best[2]:
                    best = (float(td), float(tof), float(arrival), float(dv))
    if best is None:
        return None
    return best[0], best[1], best[3]


def walk_2d(kt, perm, bridge_positions, dv_thr_arcs, dv_cap_arcs,
             verbose=False):
    """Walk perm. For each arc:
    - If position in bridge_positions: 2D search at dv_exc cap
    - Else: try find_earliest_transfer at t_ready first (cheap);
      if it fails, fall back to 2D search at dv_thr

    dv_thr_arcs[k]: per-leg cheap dv cap (default kt.dv_thr)
    dv_cap_arcs[k]: per-leg exception dv cap (default kt.dv_exc)
    """
    times = []
    tofs = []
    t_ready = 0.0
    n_arcs = len(perm) - 1
    for k in range(n_arcs):
        i, j = perm[k], perm[k + 1]
        is_bridge = k in bridge_positions
        cap_cheap = dv_thr_arcs[k] if dv_thr_arcs else kt.dv_thr
        cap_exc = dv_cap_arcs[k] if dv_cap_arcs else kt.dv_exc
        # Try cheap first via find_earliest_transfer (fast)
        if not is_bridge:
            tof_a, dv_a = find_earliest_transfer(
                kt, i, j, t_ready, cap_cheap, tof_window=30.0,
                n_steps=120)
            if tof_a is not None:
                times.append(t_ready)
                tofs.append(tof_a)
                t_ready = t_ready + tof_a
                continue
        # Bridge or cheap-FAILED: 2D search at exception cap
        # (waiting allowed)
        res = search_arc_2d(kt, i, j, t_ready, cap_exc,
                             n_td=30, n_tof=20,
                             td_max_offset=1500.0)
        if res is None:
            if verbose:
                print(f"    arc {k} ({i}→{j}) FAILED at t_ready={t_ready:.0f}",
                      flush=True)
            return times, tofs, False, k
        td, tof, dv = res
        times.append(td)
        tofs.append(tof)
        t_ready = td + tof
        if t_ready > kt.max_time + 1e-6:
            return times, tofs, False, k
    return times, tofs, True, None


def main(problem="large"):
    """Smoke test on a single assembly candidate."""
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    comp2_path = pickle.load(open(
        "/tmp/large_comp2_hamilton_3600s.pkl", "rb"))["comp_2_path"]
    bt = pickle.load(open("/tmp/large_comp2_bridge_table.pkl", "rb"))
    cycles = pickle.load(open("/tmp/large_ortools_cycles.pkl", "rb"))
    SMALL_A, SMALL_B, SMALL_C = 1, 3, 0
    cycle_a, cycle_b, cycle_c = cycles[SMALL_A], cycles[SMALL_B], cycles[SMALL_C]
    L_a, L_b, L_c = len(cycle_a), len(cycle_b), len(cycle_c)

    def rotate(cycle, entry):
        i = cycle.index(entry)
        return cycle[i:] + cycle[:i]

    # a_start, c_end, valid_cuts
    a_start = []
    for d in bt["bridges_in"].get(comp2_path[0], {}).get(SMALL_A, []):
        b = d[0]
        a = cycle_a[(cycle_a.index(b) + 1) % L_a]
        a_start.append((a, b, d))
    a_start.sort(key=lambda x: x[2][1])
    c_end = []
    for d in bt["bridges_out"].get(comp2_path[-1], {}).get(SMALL_C, []):
        a = d[0]
        b = cycle_c[(cycle_c.index(a) - 1) % L_c]
        c_end.append((a, b, d))
    c_end.sort(key=lambda x: x[2][1])
    valid_cuts = []
    for cut in range(len(comp2_path) - 1):
        n_e = comp2_path[cut]
        n_s = comp2_path[cut + 1]
        out_data = bt["bridges_out"].get(n_e, {}).get(SMALL_B, [])
        in_data = bt["bridges_in"].get(n_s, {}).get(SMALL_B, [])
        a_set = {d[0]: d for d in out_data}
        b_set = {d[0]: d for d in in_data}
        opts = []
        for a in a_set:
            b = cycle_b[(cycle_b.index(a) - 1) % L_b]
            if b in b_set:
                opts.append((a, b, a_set[a], b_set[b]))
        if opts:
            opts.sort(key=lambda x: x[2][1] + x[3][1])
            valid_cuts.append((cut, opts))

    print(f"Loaded: a_start={len(a_start)}, c_end={len(c_end)}, "
          f"valid_cuts={len(valid_cuts)}", flush=True)

    # Smoke test: try cuts one by one with cheapest options each
    best = None
    t0 = time.time()
    for ci, (cut, b_opts) in enumerate(valid_cuts):
        a_a, b_a, _ = a_start[0]
        a_c, b_c, _ = c_end[0]
        a_b, b_b, _, _ = b_opts[0]
        path_a = rotate(cycle_a, a_a)
        path_b = rotate(cycle_b, a_b)
        path_c = rotate(cycle_c, a_c)
        seg1 = comp2_path[:cut + 1]
        seg2 = comp2_path[cut + 1:]
        full_perm = path_a + seg1 + path_b + seg2 + path_c
        if len(full_perm) != kt.n or len(set(full_perm)) != kt.n:
            continue
        # Bridge positions in the perm
        L1, L2 = len(seg1), len(seg2)
        pos_b0 = L_a - 1                        # path_a[-1] → seg1[0]
        pos_b1 = L_a + L1 - 1                   # seg1[-1] → path_b[0]
        pos_b2 = L_a + L1 + L_b - 1             # path_b[-1] → seg2[0]
        pos_b3 = L_a + L1 + L_b + L2 - 1        # seg2[-1] → path_c[0]
        bridge_positions = {pos_b0, pos_b1, pos_b2, pos_b3}
        times, tofs, ok, failed_at = walk_2d(
            kt, full_perm, bridge_positions, None, None)
        if not ok:
            if ci < 5 or ci % 20 == 0:
                print(f"  cut={cut} ({ci+1}/{len(valid_cuts)}): "
                      f"walk failed at arc {failed_at} after "
                      f"{time.time()-t0:.0f}s", flush=True)
            continue
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        mk = float(f[0])
        print(f"  cut={cut} ({ci+1}/{len(valid_cuts)}): WALK OK mk={mk:.2f}, "
              f"feasible={feas}, fitness={list(f)}", flush=True)
        if feas:
            if best is None or mk < best[0]:
                best = (mk, full_perm, times, tofs)
                # Save immediately
                p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
                import json
                p.write_text(json.dumps([{
                    "decisionVector": list(x),
                    "problem": problem, "challenge": 2}]))
                print(f"    ✓ SAVED to {p}", flush=True)
                # Stop on first feasible for quick feedback
                break
    wall = time.time() - t0
    print(f"\nDone in {wall:.0f}s, best mk={best[0] if best else None}",
          flush=True)
    if best is None:
        return {"status": "no_feasible"}
    return {"problem": problem, "mk": float(best[0]), "feasible": True}


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2))
