"""Ch2 KTTSP — targeted exception-replacement via single-node re-insertion.

The 142.99 perm has 5 exception arcs at specific bridge positions.
For each exception leg (i → j), this script:
1. Removes node j from the perm (partial of 48 nodes).
2. Runs insert_lns to re-insert j at the best feasible position.
3. Re-walks chronologically; if mk < 142.99 with feasibility, banks.

The hypothesis: random or-opt doesn't find improvements at the
exception positions, but the TARGETED 1-node removal + re-insertion
explores those specific structural changes systematically.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def remove_and_reinsert(kt, perm, removed_node, verbose=False):
    """Remove `removed_node` from perm; re-insert at the best position
    by chronological walk + makespan minimisation."""
    if removed_node not in perm:
        return None, None, None
    cur = [v for v in perm if v != removed_node]
    best = None  # (mk, perm_full, times, tofs)
    for pos in range(1, len(cur) + 1):
        cand = [*cur[:pos], removed_node, *cur[pos:]]
        times, tofs, _, ok, _, _ = walk_perm_chrono(kt, cand)
        if not ok:
            continue
        mk = times[-1] + tofs[-1]
        x = times + tofs + [float(v) for v in cand]
        f = kt.fitness(x)
        if kt.is_feasible(f) and (best is None or mk < best[0]):
            best = (mk, cand, times, tofs)
            if verbose:
                print(f"    pos={pos}: mk={mk:.3f}", flush=True)
    return best if best else (None, None, None, None)


def main(inst="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
              "Salesperson Problem/problems/easy.kttsp",
         in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small"):
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm = [round(v) for v in x0[2 * n - 2:]]
    times0 = x0[:n - 1]
    tofs0 = x0[n - 1:2 * n - 2]
    initial_mk = kt.fitness(x0)[0]
    print(f"Initial: mk={initial_mk:.3f}, perm={perm}", flush=True)
    # Identify exception destinations
    exc_dests = []
    for i in range(n - 1):
        dv = kt.compute_transfer(perm[i], perm[i + 1],
                                 times0[i], tofs0[i])
        if dv > 100:
            exc_dests.append((i, perm[i], perm[i + 1], dv))
    print(f"Exception arcs: {exc_dests}", flush=True)
    best = (initial_mk, perm, times0, tofs0)
    t_total = time.time()
    for _leg_idx, i_node, j_node, dv_exc in exc_dests:
        print(f"\n--- Removing {j_node} (dest of exception arc "
              f"{i_node}→{j_node} @ {dv_exc:.1f} m/s) ---", flush=True)
        t0 = time.time()
        result = remove_and_reinsert(kt, perm, j_node, verbose=True)
        if result == (None, None, None, None) or result[0] is None:
            print("  no feasible re-insertion", flush=True)
            continue
        mk, cand_perm, times, tofs = result
        wall = time.time() - t0
        improvement = initial_mk - mk
        print(f"  best mk={mk:.3f} (Δ={improvement:.3f}), wall={wall:.1f}s",
              flush=True)
        if mk < best[0] - 0.05:
            best = (mk, cand_perm, times, tofs)
    info = {"problem": problem, "n": n,
            "wall_s": round(time.time() - t_total, 1),
            "initial_mk": round(initial_mk, 3),
            "final_mk": round(best[0], 3),
            "improvement_d": round(initial_mk - best[0], 3),
            "rank3_small_d": 111.76}
    if best[0] < initial_mk - 0.05:
        x_dec = list(best[2]) + list(best[3]) + \
            [float(v) for v in best[1]]
        f = kt.fitness(x_dec)
        if kt.is_feasible(f):
            p = Path(out) / f"{problem}.json"
            p.write_text(json.dumps([{"decisionVector": x_dec,
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            info["replaced_banked"] = True
            info["fitness"] = list(f)
    return info


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
