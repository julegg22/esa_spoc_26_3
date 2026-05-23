"""Ch2 KTTSP large — assemble feasible Hamilton path via cut+small-comp insertion.

Inputs (precomputed):
- /tmp/large_comp2_hamilton_3600s.pkl: comp 2 Hamilton path (601 nodes,
  1 INF arc somewhere)
- /tmp/large_comp2_bridge_table.pkl: per-comp-2-node bridges to/from
  each small comp
- /tmp/large_ortools_cycles.pkl: Hamilton cycles for small comps 0, 1, 3

Strategy:
  Insert 3 small comps into comp 2's Hamilton via 2 cuts (one at INF
  position) + 1 small comp at journey start or end. 5 transitions
  total; 1 saved by INF cut; 4 net exc bridges ≤ budget 5.

Arrangements tried:
  A: [small_a, seg1, small_b, seg2, small_c, seg3]   small at start
  B: [seg1, small_a, seg2, small_b, seg3, small_c]   small at end
  (3! orderings per arrangement × 2 cuts to enumerate)
"""

from __future__ import annotations

import itertools
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_ortools_hamilton import (
    build_distance_matrix, INF, SCALE,
)


def find_inf_position(comp2_path, D, node_map):
    """Return position k such that the arc (path[k], path[k+1]) is INF."""
    idx_of = {v: k for k, v in enumerate(node_map)}
    for i in range(len(comp2_path) - 1):
        a, b = comp2_path[i], comp2_path[i + 1]
        if D[idx_of[a], idx_of[b]] >= INF:
            return i
    return None


def rotate_cycle(cycle, entry):
    """Return cycle rotated so it starts at entry. Returns path
    [entry, ..., predecessor_of_entry]."""
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
    # Load
    comp2_data = pickle.load(open("/tmp/large_comp2_hamilton_3600s.pkl",
                                    "rb"))
    comp2_path = comp2_data["comp_2_path"]
    print(f"Comp 2 Hamilton: {len(comp2_path)} nodes, "
          f"INF arcs: {comp2_data['inf_arcs']}", flush=True)
    bt = pickle.load(open("/tmp/large_comp2_bridge_table.pkl", "rb"))
    bridges_out = bt["bridges_out"]
    bridges_in = bt["bridges_in"]
    cycles = pickle.load(open("/tmp/large_ortools_cycles.pkl", "rb"))
    small_comps = [c for c in cycles if cycles[c] is not None]
    print(f"Small comps: {small_comps}, sizes "
          f"{[len(cycles[c]) for c in small_comps]}", flush=True)
    # Find INF arc position
    g = pickle.load(open("/tmp/large_cheap_arc_graph_knn200.pkl", "rb"))
    from esa_spoc_26.ch2_component_aware import find_components
    comps = find_components(g["cheap_edges"], kt.n)
    comps = {int(k): v for k, v in comps.items()}
    D, node_map = build_distance_matrix(comps[2], g["cheap_edges"],
                                          kt.dv_thr)
    inf_pos = find_inf_position(comp2_path, D, node_map)
    print(f"INF arc position in comp 2 Hamilton: {inf_pos}", flush=True)

    # Helper: get available (a, b) entries for small comp X with
    # constraints (n_in_c2 must bridge to a, and b must bridge to
    # n_out_c2)
    def find_small_entries(small_X, n_in_c2, n_out_c2):
        """Return list of (a, b) where a=entry to X, b=exit, both
        used such that n_in_c2 → a feasible and b → n_out_c2 feasible
        AND b is cycle-predecessor of a."""
        cycle_X = cycles[small_X]
        L = len(cycle_X)
        # bridges from n_in_c2 to X
        out_data = bridges_out.get(n_in_c2, {}).get(small_X, [])
        # bridges from X to n_out_c2
        in_data = bridges_in.get(n_out_c2, {}).get(small_X, [])
        a_candidates = {d[0]: d for d in out_data}  # entries
        b_candidates = {d[0]: d for d in in_data}  # exits
        result = []
        for a in a_candidates:
            ai = cycle_X.index(a)
            b = cycle_X[(ai - 1) % L]  # cycle predecessor
            if b in b_candidates:
                result.append((a, b, a_candidates[a], b_candidates[b]))
        return result

    # Also entries for small comp at START of journey
    def find_small_start(small_X, n_out_c2):
        """Small comp X at journey start: exit → n_out_c2.
        Entry is the journey start (any node)."""
        cycle_X = cycles[small_X]
        L = len(cycle_X)
        in_data = bridges_in.get(n_out_c2, {}).get(small_X, [])
        b_candidates = {d[0]: d for d in in_data}
        result = []
        for b in b_candidates:
            bi = cycle_X.index(b)
            a = cycle_X[(bi + 1) % L]  # next after b
            result.append((a, b, None, b_candidates[b]))
        return result

    def find_small_end(small_X, n_in_c2):
        """Small comp X at journey end: n_in_c2 → entry. Exit is
        journey end."""
        cycle_X = cycles[small_X]
        L = len(cycle_X)
        out_data = bridges_out.get(n_in_c2, {}).get(small_X, [])
        a_candidates = {d[0]: d for d in out_data}
        result = []
        for a in a_candidates:
            ai = cycle_X.index(a)
            b = cycle_X[(ai - 1) % L]
            result.append((a, b, a_candidates[a], None))
        return result

    print(f"\nSearching cut+assignment...", flush=True)

    best = None
    t0 = time.time()
    n_tried = 0

    # Arrangement A: [small_a, seg1, small_b, seg2, small_c, seg3]
    # 2 cuts inside comp 2 Hamilton (1 at INF, 1 elsewhere)
    # Need:
    #  small_a (start): exit_a → comp2_path[0]
    #  small_b (between seg1, seg2): comp2_path[cut1_end] → small_b
    #    entry_b, exit_b → comp2_path[cut1_end+1]
    #  small_c (between seg2, seg3): comp2_path[cut2_end] → small_c
    #    entry_c, exit_c → comp2_path[cut2_end+1]

    # Iterate over cut positions: 1 is fixed at INF, the other varies
    fixed_inf = inf_pos
    for cut_other in range(len(comp2_path) - 1):
        if cut_other == fixed_inf:
            continue
        cut1, cut2 = sorted([fixed_inf, cut_other])
        # Segments:
        seg1 = comp2_path[:cut1 + 1]
        seg2 = comp2_path[cut1 + 1:cut2 + 1]
        seg3 = comp2_path[cut2 + 1:]
        n1_end = seg1[-1]
        n2_start = seg2[0]
        n2_end = seg2[-1]
        n3_start = seg3[0]
        # For each assignment of small_comp_perm to roles (start, middle1, middle2)
        for perm_assign in itertools.permutations(small_comps):
            small_a, small_b, small_c = perm_assign
            # small_a at start: a-entry is journey start, a-exit → seg1[0] = comp2_path[0]
            cand_a = find_small_start(small_a, comp2_path[0])
            # small_b between seg1 and seg2: n1_end → b-entry, b-exit → n2_start
            cand_b = find_small_entries(small_b, n1_end, n2_start)
            # small_c between seg2 and seg3: n2_end → c-entry, c-exit → n3_start
            cand_c = find_small_entries(small_c, n2_end, n3_start)
            n_tried += 1
            if not cand_a or not cand_b or not cand_c:
                continue
            # Pick cheapest representative per candidate
            (a_a, b_a, _, in_a) = cand_a[0]
            (a_b, b_b, out_b, in_b) = cand_b[0]
            (a_c, b_c, out_c, in_c) = cand_c[0]
            # Construct full perm
            path_a = rotate_cycle(cycles[small_a], a_a)
            path_b = rotate_cycle(cycles[small_b], a_b)
            path_c = rotate_cycle(cycles[small_c], a_c)
            full_perm = (path_a + seg1 + path_b + seg2 + path_c + seg3)
            if len(full_perm) != kt.n or len(set(full_perm)) != kt.n:
                continue
            # Walk
            times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
                kt, full_perm, tof_window=30.0, n_steps=200)
            if not walk_ok or not times:
                continue
            x = times + tofs + [float(v) for v in full_perm]
            f = kt.fitness(x)
            feas = kt.is_feasible(f)
            mk = float(f[0])
            if feas:
                if best is None or mk < best[0]:
                    print(f"  [A] cut@INF={fixed_inf}, cut2={cut_other}, "
                          f"assignment={perm_assign}: FEASIBLE mk={mk:.2f}",
                          flush=True)
                    best = (mk, full_perm, list(times), list(tofs),
                             "A", fixed_inf, cut_other, perm_assign)

    # Arrangement B: same with small at end instead of start
    for cut_other in range(len(comp2_path) - 1):
        if cut_other == fixed_inf:
            continue
        cut1, cut2 = sorted([fixed_inf, cut_other])
        seg1 = comp2_path[:cut1 + 1]
        seg2 = comp2_path[cut1 + 1:cut2 + 1]
        seg3 = comp2_path[cut2 + 1:]
        n1_end = seg1[-1]
        n2_start = seg2[0]
        n2_end = seg2[-1]
        n3_start = seg3[0]
        n3_end = seg3[-1]
        for perm_assign in itertools.permutations(small_comps):
            small_a, small_b, small_c = perm_assign  # a between 1-2, b between 2-3, c at end
            cand_a = find_small_entries(small_a, n1_end, n2_start)
            cand_b = find_small_entries(small_b, n2_end, n3_start)
            cand_c = find_small_end(small_c, n3_end)
            n_tried += 1
            if not cand_a or not cand_b or not cand_c:
                continue
            a_a, b_a, _, _ = cand_a[0]
            a_b, b_b, _, _ = cand_b[0]
            a_c, b_c, _, _ = cand_c[0]
            path_a = rotate_cycle(cycles[small_a], a_a)
            path_b = rotate_cycle(cycles[small_b], a_b)
            path_c = rotate_cycle(cycles[small_c], a_c)
            full_perm = (seg1 + path_a + seg2 + path_b + seg3 + path_c)
            if len(full_perm) != kt.n or len(set(full_perm)) != kt.n:
                continue
            times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
                kt, full_perm, tof_window=30.0, n_steps=200)
            if not walk_ok or not times:
                continue
            x = times + tofs + [float(v) for v in full_perm]
            f = kt.fitness(x)
            feas = kt.is_feasible(f)
            mk = float(f[0])
            if feas:
                if best is None or mk < best[0]:
                    print(f"  [B] cut@INF={fixed_inf}, cut2={cut_other}, "
                          f"assignment={perm_assign}: FEASIBLE mk={mk:.2f}",
                          flush=True)
                    best = (mk, full_perm, list(times), list(tofs),
                             "B", fixed_inf, cut_other, perm_assign)

    wall = time.time() - t0
    print(f"\nSearch wall: {wall:.0f}s, tried={n_tried}", flush=True)
    if best is None:
        return {"status": "no_feasible_assembly"}
    mk, perm, times, tofs, arr, c1, c2, assignment = best
    x = times + tofs + [float(v) for v in perm]
    p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
    p.write_text(json.dumps([{"decisionVector": list(x),
                              "problem": problem,
                              "challenge": CHALLENGE}]))
    print(f"BANKED mk={mk:.2f} (arrangement={arr}, cuts=({c1},{c2}), "
          f"assignment={assignment})", flush=True)
    return {"problem": problem, "n": kt.n, "mk": float(mk),
            "feasible": True, "banked": str(p)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
