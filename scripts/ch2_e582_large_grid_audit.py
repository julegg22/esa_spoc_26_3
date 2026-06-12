"""E-045 PART A — Ch2 LARGE: tof-grid resolution audit.

Before building an epoch-aware LKH cost matrix, audit the evaluator
(methodology trigger). The bank walk and all our diagnostics use
find_earliest_transfer with tof_window=12, n_steps=120 -> 0.1d grid.
r1=424.62d implies 0.404 d/node, below the chainable phase-adjacent
floor (0.857d, E-044). The CHEAPEST explanation for a 2.5x gap is that
the coarse grid is missing very-short-tof cheap transfers. Test it.

For a sample of cheap-adjacent (i,j) pairs at the node's bank epoch,
compare the minimum CHEAP tof found by:
  - coarse:  window=12, n_steps=120   (0.100 d step)   [the bank grid]
  - fine:    window=12, n_steps=1200  (0.010 d step)
  - short:   window=2,  n_steps=400    (0.005 d step, short-tof zoom)
If fine/short find materially shorter cheap tofs than coarse, the grid
is the bottleneck and r1 may be reachable by re-walking on a finer grid.
If not, the 0.404 d/node floor is NOT a discretization artifact and
must come from a fundamentally different ordering/model.

Read-only. Writes nothing. Prints a summary table.
"""
import json
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
ADJ = "/tmp/ch2_e533_large_adj.npz"
SAMPLE = 300
SEED = 0


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    times0 = [float(v) for v in bank[:n - 1]]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]
    # node -> bank departure epoch (last node never departs)
    epoch = {perm0[k]: times0[k] for k in range(n - 1)}

    d = np.load(ADJ)
    cheap = d["cheap"]
    labels = d["labels"]

    rng = np.random.default_rng(SEED)
    # sample cheap-adjacent ordered pairs where i has a bank epoch
    pairs = []
    src = rng.permutation(n - 1)  # exclude last (no epoch); index into perm
    for k in src:
        i = perm0[k]
        nbrs = np.where(cheap[i])[0]
        nbrs = nbrs[nbrs != i]
        if len(nbrs) == 0:
            continue
        j = int(rng.choice(nbrs))
        pairs.append((i, j))
        if len(pairs) >= SAMPLE:
            break

    print(f"[E-582] grid audit n={n} sample={len(pairs)} pairs "
          f"(cheap-adjacent, at bank epoch)", flush=True)
    grids = {
        "coarse": (12.0, 120),   # 0.100 d
        "fine":   (12.0, 1200),  # 0.010 d
        "short":  (2.0, 400),    # 0.005 d
    }
    res = {g: [] for g in grids}
    both_cheap = 0
    t0 = time.time()
    for (i, j) in pairs:
        t = epoch[i]
        row = {}
        for g, (win, steps) in grids.items():
            tof, dv = find_earliest_transfer(kt, i, j, t, kt.dv_thr, win, steps)
            row[g] = tof
        # only compare where coarse found a cheap transfer
        if row["coarse"] is not None:
            both_cheap += 1
            for g in grids:
                if row[g] is not None:
                    res[g].append(row[g])
        else:
            # coarse missed but finer found -> grid UNDER-finding feasibility
            if row["fine"] is not None or row["short"] is not None:
                res.setdefault("_coarse_missed_feasible", []).append((i, j))

    dt = time.time() - t0
    print(f"[E-582] probed in {dt:.0f}s. coarse-cheap pairs={both_cheap}",
          flush=True)
    # For pairs cheap on coarse, compare min cheap tof across grids
    # (paired: same pair set = those where coarse found cheap)
    coarse = np.array(res["coarse"])
    print(f"  coarse  min-cheap-tof: mean={coarse.mean():.4f} "
          f"median={np.median(coarse):.4f} min={coarse.min():.4f}d", flush=True)
    # paired fine/short on the SAME pairs as coarse
    fine_paired, short_paired, cm = [], [], []
    for (i, j) in pairs:
        t = epoch[i]
        c, _ = find_earliest_transfer(kt, i, j, t, kt.dv_thr, 12.0, 120)
        if c is None:
            continue
        f, _ = find_earliest_transfer(kt, i, j, t, kt.dv_thr, 12.0, 1200)
        s, _ = find_earliest_transfer(kt, i, j, t, kt.dv_thr, 2.0, 400)
        fine_paired.append(f if f is not None else c)
        short_paired.append(s if s is not None else c)
        cm.append(c)
    cm = np.array(cm)
    fp = np.array(fine_paired)
    sp = np.array(short_paired)
    print(f"  PAIRED (same {len(cm)} pairs, coarse-cheap):", flush=True)
    print(f"    coarse mean={cm.mean():.4f}  fine mean={fp.mean():.4f}  "
          f"short mean={sp.mean():.4f}", flush=True)
    print(f"    fine vs coarse: mean delta={ (cm-fp).mean():.4f}d  "
          f"max improvement={ (cm-fp).max():.4f}d", flush=True)
    print(f"    short vs coarse: mean delta={ (cm-sp).mean():.4f}d  "
          f"max improvement={ (cm-sp).max():.4f}d", flush=True)
    cm2 = np.where((cm - np.minimum(fp, sp)) > 0.05)[0]
    print(f"    pairs improved >0.05d by finer grid: {len(cm2)}/{len(cm)}",
          flush=True)
    missed = res.get("_coarse_missed_feasible", [])
    print(f"  coarse missed feasibility (finer found cheap): {len(missed)}",
          flush=True)
    print("\n[E-582] VERDICT: if mean-delta and improved-count are ~0, the "
          "0.1d grid is NOT the bottleneck; r1's 0.404 d/node needs a "
          "different ordering/model, not a finer grid.", flush=True)


if __name__ == "__main__":
    main()
