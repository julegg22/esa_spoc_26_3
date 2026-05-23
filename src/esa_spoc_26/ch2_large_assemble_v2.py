"""Ch2 KTTSP large — assembly v2 (FORCED ASSIGNMENT).

Arrangement: [small_a, seg1, small_b, seg2, small_c]
  - small_a = comp 1 (FORCED: only comp 1 bridges to comp2_path[0]=582)
  - small_c = comp 0 (FORCED: only comp 0 bridges from comp2_path[-1]=205)
  - small_b = comp 3 (forced remaining)

4 inter-comp transitions + 1 INF arc inside comp 2 = 5 excs = budget.

Search: for each cut position in comp 2 (600 candidates), check
if small comp 3 has valid (a, b) cycle-predecessor pair satisfying
the bridges. Pick the assembly with lowest walked makespan.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


SMALL_A_ID = 1  # bridges to comp2_path[0]
SMALL_B_ID = 3  # in the middle
SMALL_C_ID = 0  # bridges from comp2_path[-1]


def rotate_cycle(cycle, entry):
    if entry not in cycle:
        return None
    ei = cycle.index(entry)
    return cycle[ei:] + cycle[:ei]


def main(problem="large"):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    comp2_path = pickle.load(open(
        "/tmp/large_comp2_hamilton_3600s.pkl", "rb"))["comp_2_path"]
    bt = pickle.load(open("/tmp/large_comp2_bridge_table.pkl", "rb"))
    bridges_out = bt["bridges_out"]
    bridges_in = bt["bridges_in"]
    cycles = pickle.load(open("/tmp/large_ortools_cycles.pkl", "rb"))
    cycle_a = cycles[SMALL_A_ID]
    cycle_b = cycles[SMALL_B_ID]
    cycle_c = cycles[SMALL_C_ID]
    L_a, L_b, L_c = len(cycle_a), len(cycle_b), len(cycle_c)
    print(f"Cycles: A={SMALL_A_ID}({L_a}) B={SMALL_B_ID}({L_b}) C={SMALL_C_ID}({L_c})",
          flush=True)
    print(f"Comp2 path[0]={comp2_path[0]}, path[-1]={comp2_path[-1]}",
          flush=True)

    # Pre-compute valid (a, b) options for small_a (start)
    # small_a.exit (b) → path[0] required.
    in_to_start = bridges_in.get(comp2_path[0], {}).get(SMALL_A_ID, [])
    a_start_options = []  # (entry, exit, bridge_info)
    for d in in_to_start:
        b = d[0]
        bi = cycle_a.index(b)
        a = cycle_a[(bi + 1) % L_a]
        a_start_options.append((a, b, d))
    print(f"Small_a={SMALL_A_ID} at start: {len(a_start_options)} options",
          flush=True)

    # small_c (end): path[-1] → small_c.entry (a). Exit is journey end.
    out_from_end = bridges_out.get(comp2_path[-1], {}).get(SMALL_C_ID, [])
    c_end_options = []
    for d in out_from_end:
        a = d[0]
        ai = cycle_c.index(a)
        b = cycle_c[(ai - 1) % L_c]
        c_end_options.append((a, b, d))
    print(f"Small_c={SMALL_C_ID} at end: {len(c_end_options)} options",
          flush=True)

    if not a_start_options or not c_end_options:
        return {"status": "missing_endpoint_bridges"}

    # For each cut position, find valid small_b (=3) options
    valid_cuts = []
    for cut in range(len(comp2_path) - 1):
        n_a_end = comp2_path[cut]
        n_a_start_next = comp2_path[cut + 1]
        # small_b entry a, exit b cycle-pred of a
        out_data = bridges_out.get(n_a_end, {}).get(SMALL_B_ID, [])
        in_data = bridges_in.get(n_a_start_next, {}).get(SMALL_B_ID, [])
        a_set = {d[0]: d for d in out_data}
        b_set = {d[0]: d for d in in_data}
        options = []
        for a in a_set:
            ai = cycle_b.index(a)
            b = cycle_b[(ai - 1) % L_b]
            if b in b_set:
                options.append((a, b, a_set[a], b_set[b]))
        if options:
            valid_cuts.append((cut, options))
    print(f"Valid cuts admitting small_b={SMALL_B_ID}: {len(valid_cuts)}/600",
          flush=True)

    print(f"\nAssembling and walking (early-exit on first feasible)...",
          flush=True)
    best = None
    t0 = time.time()
    n_tried = 0
    n_walked = 0
    n_feas = 0
    a_start_options.sort(key=lambda x: x[2][1])  # by dv
    # Try 1 a_start × 1 c_end × 1 b_opt per cut for speed
    for cut, b_options in valid_cuts:
        seg1 = comp2_path[:cut + 1]
        seg2 = comp2_path[cut + 1:]
        a_a, b_a, _ = a_start_options[0]
        path_a = rotate_cycle(cycle_a, a_a)
        a_c, b_c, _ = c_end_options[0]
        path_c = rotate_cycle(cycle_c, a_c)
        a_b, b_b, _, _ = b_options[0]
        path_b = rotate_cycle(cycle_b, a_b)
        full_perm = path_a + seg1 + path_b + seg2 + path_c
        n_tried += 1
        if len(full_perm) != kt.n or len(set(full_perm)) != kt.n:
            continue
        # Fast walk (lower n_steps for speed)
        times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
            kt, full_perm, tof_window=30.0, n_steps=80)
        if not walk_ok or not times:
            if n_tried % 20 == 0:
                print(f"  cut={cut} ({n_tried}/{len(valid_cuts)}): walk failed",
                      flush=True)
            continue
        n_walked += 1
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        mk = float(f[0])
        if feas:
            n_feas += 1
            print(f"  ✓ cut={cut}: FEASIBLE mk={mk:.2f}, "
                  f"fitness={list(f)}", flush=True)
            if best is None or mk < best[0]:
                best = (mk, full_perm, list(times), list(tofs))
                # Early exit on first feasible
                break
        else:
            if n_walked <= 5 or n_walked % 10 == 0:
                print(f"  cut={cut} ({n_tried}/{len(valid_cuts)}): "
                      f"INFEAS mk={mk:.2f}, fitness={list(f)}",
                      flush=True)
    wall = time.time() - t0
    print(f"\nSearch wall: {wall:.0f}s; tried={n_tried}, walked={n_walked}, "
          f"feasible={n_feas}", flush=True)
    if best is None:
        return {"status": "no_feasible_assembly"}
    mk, perm, times, tofs = best
    x = times + tofs + [float(v) for v in perm]
    p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
    p.write_text(json.dumps([{"decisionVector": list(x),
                              "problem": problem,
                              "challenge": CHALLENGE}]))
    print(f"BANKED: {p}, mk={mk:.4f}", flush=True)
    return {"problem": problem, "n": kt.n, "mk": float(mk),
            "feasible": True, "banked": str(p)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
