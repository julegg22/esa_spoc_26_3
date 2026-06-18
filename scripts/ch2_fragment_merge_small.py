"""E-655 lever #1 (from E-654 audit): FRAGMENT-MERGE reformulation for Ch2-small.

Audit found: loss is epoch-phasing + merging the assignment's cheap-min-tof FRAGMENTS
(22 subtours) into one tour — NOT edge choice. This builds a tour by RESPECTING that
fragment structure: (1) Hungarian assignment on per-epoch-min cheap-tof -> subtour cycles,
(2) break each cycle into a chain (drop its longest edge), (3) merge the chains into ONE
order (greedy nearest-endpoint + randomized restarts + orientation), (4) faithfully walk
(walk_perm_chrono) -> official makespan. Tests whether the fragment structure yields an
order our local search never found (<112.996, and ideally <111.76=rank4 / <110.88=rank3).

Positive control: the assignment cost matrix reproduces sane min-tofs. Guard: dumps best
to /tmp, banks NOTHING (caller decides). Usage: python ch2_fragment_merge_small.py [nrestarts=2000]
"""
import sys, json, time, random
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from scipy.optimize import linear_sum_assignment
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
STRICT = dict(tof_window=12.0, n_steps=200, wait_steps=8, wait_dt=0.5)


def fragments_from_assignment(cost):
    n = cost.shape[0]; BIG = 1e6
    C = np.where(np.isfinite(cost), cost, BIG); np.fill_diagonal(C, BIG)
    ri, ci = linear_sum_assignment(C)
    succ = {int(i): int(j) for i, j in zip(ri, ci)}
    seen = set(); frags = []
    for s in range(n):
        if s in seen:
            continue
        cyc = []; x = s
        while x not in seen:
            seen.add(x); cyc.append(x); x = succ[x]
        frags.append(cyc)
    # break each cycle into a chain by dropping its longest edge
    chains = []
    for cyc in frags:
        if len(cyc) == 1:
            chains.append(cyc); continue
        worst = max(range(len(cyc)), key=lambda k: C[cyc[k], cyc[(k + 1) % len(cyc)]])
        chains.append(cyc[worst + 1:] + cyc[:worst + 1])
    return chains, C


def merge_chains(chains, C, rng):
    """Greedy: start from a random chain, repeatedly append the chain whose head/tail is
    cheapest to connect to the current tail (orient as needed)."""
    chains = [list(c) for c in chains]
    rng.shuffle(chains)
    tour = chains.pop(0)
    if rng.random() < 0.5:
        tour = tour[::-1]
    while chains:
        tail = tour[-1]; best = None
        for idx, ch in enumerate(chains):
            for orient in (0, 1):
                head = ch[0] if orient == 0 else ch[-1]
                c = C[tail, head]
                if best is None or c < best[0]:
                    best = (c, idx, orient)
        _, idx, orient = best
        ch = chains.pop(idx)
        tour += (ch if orient == 0 else ch[::-1])
    return tour


def main(nrestarts=2000):
    kt = KTTSP(INST); n = kt.n
    d = np.load('/tmp/ch2_small_tcoupled_ultrafine.npz'); cheap = d['cheap']
    cost = np.min(cheap, axis=2)
    bank = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
    chains, C = fragments_from_assignment(cost)
    print(f"[E-655] n={n} bank={bank:.3f} | assignment -> {len(chains)} fragments "
          f"(sizes {sorted((len(c) for c in chains), reverse=True)[:8]})", flush=True)
    # positive control: a feasible walk of SOME order reproduces a sane makespan
    rng = random.Random(0)
    best_mk = 1e9; best_order = None; nfeas = 0; t0 = time.time()
    for r in range(nrestarts):
        order = merge_chains(chains, C, rng)
        if len(set(order)) != n:
            continue
        times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, order, **STRICT)
        if not ok:
            continue
        nfeas += 1
        x = list(times) + list(tofs) + [float(p) for p in order]
        f = kt.fitness(x); mk = float(f[0])
        if kt.is_feasible(f) and mk < best_mk:
            best_mk = mk; best_order = x
            tag = " *** <BANK" if mk < bank else ""
            print(f"  [r{r}] feasible mk={mk:.3f} (bank {bank:.3f}, {mk-bank:+.3f}){tag}", flush=True)
        if r % 200 == 0 and r:
            print(f"  [r{r}] feasible={nfeas} best={best_mk:.3f} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[DONE] {nfeas}/{nrestarts} feasible merges | best mk={best_mk:.3f} vs bank {bank:.3f} "
          f"| rank4=111.76 rank3=110.88", flush=True)
    if best_order is not None and best_mk < bank - 1e-4:
        json.dump({"makespan": best_mk, "decisionVector": best_order},
                  open('/tmp/ch2_small_fragmerge_best.json', 'w'))
        verdict = ("BEATS rank4 111.76!" if best_mk < 111.76 else "beats bank")
        print(f"  -> {verdict}; dumped /tmp/ch2_small_fragmerge_best.json (guard-bank decision to caller)", flush=True)
    else:
        print(f"  -> fragment-merge did NOT beat bank; the merge needs epoch-aware DP (lever #2), "
              f"OR the fragment structure isn't the lever. INFO: best feasible merge = {best_mk:.3f}", flush=True)


if __name__ == "__main__":
    nr = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    main(nr)
