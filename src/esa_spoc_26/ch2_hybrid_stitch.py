"""Ch2 KTTSP large — hybrid stitch: comp 2 path + 3 cycles.

Comp 2 (601 nodes) admits a Hamilton PATH (with 1 INF arc, accepted
as an internal exception bridge); a CYCLE has 3+ INF arcs (too
many). Comps 0/1/3 (150 each) admit Hamilton CYCLES (rotatable
endpoints).

Stitch:
- Start with comp 2's Hamilton path (fixed start, fixed end).
- For each subsequent small comp k, find a bridge from prev end
  to ANY cycle member; that's the new start; cycle predecessor is
  the new end.
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
from esa_spoc_26.ch2_ortools_cycle import (
    find_bridge, rotate_cycle_to_endpoints,
)


def main(problem="large",
         path_cache="/tmp/large_ortools_intra_paths.pkl",
         cycle_cache="/tmp/large_ortools_cycles.pkl"):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    with open(path_cache, "rb") as f:
        paths = pickle.load(f)
    with open(cycle_cache, "rb") as f:
        cycles = pickle.load(f)
    # Identify: comp 2 = Hamilton path, comps 0/1/3 = cycles
    path_comp = 2
    cycle_comps = [c for c in cycles if c != path_comp and cycles[c] is not None]
    print(f"Path comp: {path_comp} ({len(paths[path_comp])} nodes)",
          flush=True)
    print(f"Cycle comps: {cycle_comps} sizes {[len(cycles[c]) for c in cycle_comps]}",
          flush=True)

    comp2_path = paths[path_comp]
    # Try orderings of cycle_comps after comp 2
    best = None
    t0 = time.time()
    for ordering in itertools.permutations(cycle_comps):
        full_perm = list(comp2_path)
        ok = True
        for k, ci in enumerate(ordering):
            src = full_perm[-1]
            cycle = cycles[ci]
            br = find_bridge(kt, int(src), cycle)
            if br is None:
                ok = False
                break
            dst, dv, td, tof = br
            # Rotate cycle so it starts at dst, ends at dst's cycle
            # predecessor
            ci_dst = cycle.index(dst)
            cycle_end = cycle[(ci_dst - 1) % len(cycle)]
            path_k = rotate_cycle_to_endpoints(cycle, dst, cycle_end)
            if path_k is None:
                ok = False
                break
            full_perm.extend(path_k)
        if not ok:
            continue
        if len(full_perm) != kt.n:
            continue
        print(f"  ordering {ordering}: stitched, walking...",
              flush=True)
        # Walk
        times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
            kt, full_perm, tof_window=30.0, n_steps=200)
        if not walk_ok or not times:
            print(f"    walk failed", flush=True)
            continue
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        mk = float(f[0])
        print(f"    walk mk={mk:.4f}, feas={feas}, fitness={list(f)}",
              flush=True)
        if feas:
            if best is None or mk < best[0]:
                best = (mk, full_perm, list(times), list(tofs), ordering)
                print(f"    ✓ NEW BEST mk={mk:.4f}", flush=True)
    wall = time.time() - t0
    print(f"\nSearch wall: {wall:.0f}s", flush=True)
    if best is None:
        return {"status": "no_feasible"}
    mk, perm, times, tofs, ordering = best
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    print(f"BEST FEASIBLE: mk={mk:.4f}, ordering={ordering}",
          flush=True)
    p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
    p.write_text(json.dumps([{"decisionVector": list(x),
                              "problem": problem,
                              "challenge": CHALLENGE}]))
    print(f"BANKED: {p}", flush=True)
    return {"problem": problem, "n": kt.n, "mk": float(mk),
            "feasible": True, "banked": str(p)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
