"""Ch2 KTTSP large — walker that uses bridge_table (td, tof) hints.

walk_perm_chrono greedies tof at t_ready and misses windows where
bridge requires departing later than t_ready. Use the bridge table's
prescribed (td, tof) for the bridges and greedy for intra-component
arcs.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def walk_with_bridges(kt, perm, bridge_positions, bridge_hints,
                       tof_window=20.0, n_steps=120, max_wait=1500):
    """Walk perm. For arcs at positions in bridge_positions, use
    bridge_hints[pos] = (td_pref, tof_pref). For others, use
    find_earliest_transfer at t_ready (cheap → exc fallback).

    max_wait: how much we're willing to wait at a node before a bridge.

    Returns (times, tofs, ok).
    """
    times = []
    tofs = []
    t_ready = 0.0
    for k in range(len(perm) - 1):
        i, j = perm[k], perm[k + 1]
        if k in bridge_positions:
            td_pref, tof_pref = bridge_hints[k]
            td_use = max(t_ready, td_pref)
            if td_use - t_ready > max_wait:
                return times, tofs, False
            if td_use + tof_pref > kt.max_time:
                return times, tofs, False
            dv = kt.compute_transfer(i, j, float(td_use), float(tof_pref))
            if dv > kt.dv_exc + 1e-6:
                # Fall back to scanning at t_ready (cheap, then exc)
                tof_a, dv_a = find_earliest_transfer(
                    kt, i, j, t_ready, kt.dv_thr, tof_window, n_steps)
                if tof_a is None:
                    tof_a, dv_a = find_earliest_transfer(
                        kt, i, j, t_ready, kt.dv_exc, tof_window, n_steps)
                if tof_a is None:
                    return times, tofs, False
                times.append(t_ready)
                tofs.append(tof_a)
                t_ready = t_ready + tof_a
            else:
                times.append(td_use)
                tofs.append(tof_pref)
                t_ready = td_use + tof_pref
        else:
            # Greedy at t_ready — cheap first, exc fallback
            tof_a, _ = find_earliest_transfer(
                kt, i, j, t_ready, kt.dv_thr, tof_window, n_steps)
            if tof_a is None:
                tof_a, _ = find_earliest_transfer(
                    kt, i, j, t_ready, kt.dv_exc, tof_window, n_steps)
            if tof_a is None:
                return times, tofs, False
            times.append(t_ready)
            tofs.append(tof_a)
            t_ready = t_ready + tof_a
        if t_ready > kt.max_time:
            return times, tofs, False
    return times, tofs, True


def main(problem="large"):
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

    # small_a at start (cycle_a entered at a, exits at b → comp2_path[0])
    a_start = []
    for d in bt["bridges_in"].get(comp2_path[0], {}).get(SMALL_A, []):
        b = d[0]
        a = cycle_a[(cycle_a.index(b) + 1) % L_a]
        # The bridge hint: b → comp2_path[0] with (td, tof) from d
        a_start.append((a, b, d))  # d = (b, dv, td, tof)
    a_start.sort(key=lambda x: x[2][1])  # cheapest dv first

    # small_c at end
    c_end = []
    for d in bt["bridges_out"].get(comp2_path[-1], {}).get(SMALL_C, []):
        a = d[0]
        b = cycle_c[(cycle_c.index(a) - 1) % L_c]
        # The bridge hint: comp2_path[-1] → a with (td, tof) from d
        c_end.append((a, b, d))
    c_end.sort(key=lambda x: x[2][1])

    # For each valid cut, find small_b options
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

    print(f"a_start={len(a_start)}, c_end={len(c_end)}, "
          f"valid_cuts={len(valid_cuts)}", flush=True)

    best = None
    t0 = time.time()
    n_tried = 0
    n_walk_ok = 0
    n_feas = 0
    for cut, b_opts in valid_cuts:
        seg1 = comp2_path[:cut + 1]
        seg2 = comp2_path[cut + 1:]
        for a_a, b_a, d_a in a_start[:5]:
            path_a = rotate(cycle_a, a_a)
            for a_c, b_c, d_c in c_end[:5]:
                path_c = rotate(cycle_c, a_c)
                for a_b, b_b, d_b_out, d_b_in in b_opts[:3]:
                    path_b = rotate(cycle_b, a_b)
                    full_perm = path_a + seg1 + path_b + seg2 + path_c
                    n_tried += 1
                    if len(full_perm) != kt.n or len(set(full_perm)) != kt.n:
                        continue
                    # Bridge positions in full_perm:
                    # path_a is positions 0..L_a-1
                    # bridge 0: position L_a - 1 (last of path_a → seg1[0])
                    # seg1: positions L_a .. L_a + len(seg1) - 1
                    # bridge 1: position L_a + len(seg1) - 1 (seg1[-1] → path_b[0])
                    # path_b
                    # bridge 2: similar
                    # seg2
                    # bridge 3: similar
                    L1, L2 = len(seg1), len(seg2)
                    pos_b0 = L_a - 1
                    pos_b1 = L_a + L1 - 1
                    pos_b2 = L_a + L1 + L_b - 1
                    pos_b3 = L_a + L1 + L_b + L2 - 1
                    # d_a = (b_a (exit of small_a), dv, td, tof) for b_a → comp2_path[0]
                    # d_b_out = (a_b (entry of small_b), dv, td, tof) for seg1[-1] → a_b
                    # d_b_in = (b_b (exit of small_b), dv, td, tof) for b_b → seg2[0]
                    # d_c = (a_c (entry of small_c), dv, td, tof) for comp2_path[-1] → a_c
                    bridge_positions = {pos_b0, pos_b1, pos_b2, pos_b3}
                    bridge_hints = {
                        pos_b0: (d_a[2], d_a[3]),     # b_a → comp2_path[0]
                        pos_b1: (d_b_out[2], d_b_out[3]),
                        pos_b2: (d_b_in[2], d_b_in[3]),
                        pos_b3: (d_c[2], d_c[3]),
                    }
                    times, tofs, walk_ok = walk_with_bridges(
                        kt, full_perm, bridge_positions, bridge_hints,
                        tof_window=30.0, n_steps=100, max_wait=2000)
                    if not walk_ok or not times:
                        continue
                    n_walk_ok += 1
                    x = times + tofs + [float(v) for v in full_perm]
                    f = kt.fitness(x)
                    feas = kt.is_feasible(f)
                    mk = float(f[0])
                    if feas:
                        n_feas += 1
                        print(f"  ✓ cut={cut}: mk={mk:.2f}, "
                              f"fitness={list(f)}", flush=True)
                        if best is None or mk < best[0]:
                            best = (mk, full_perm, times, tofs)
                            # Save immediately
                            p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
                            p.write_text(json.dumps([{
                                "decisionVector": list(x),
                                "problem": problem,
                                "challenge": CHALLENGE}]))
                            print(f"    SAVED to {p}", flush=True)
                    else:
                        if n_walk_ok <= 5:
                            print(f"  cut={cut}: walked, infeas "
                                  f"fitness={list(f)}", flush=True)
    wall = time.time() - t0
    print(f"\nDone in {wall:.0f}s; tried={n_tried}, walk_ok={n_walk_ok}, "
          f"feasible={n_feas}", flush=True)
    if best is None:
        return {"status": "no_feasible"}
    return {"problem": problem, "mk": float(best[0]),
            "feasible": True}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
