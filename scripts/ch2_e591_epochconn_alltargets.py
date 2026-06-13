"""E-591 (decisive) — ALL-targets cheap-transfer check for the flagged
heavy nodes 739, 343, 753 (and a few extra heavy sources).

The main scan (ch2_e591_epochconn_heavy.py) uses a 25-node random target
sample, which could systematically miss a node's few true cheap neighbors
in a sparse cheap-graph. This script removes that risk for the decisive
nodes: at a coarse epoch grid spanning [0, max_time], it scans ALL 1050
target nodes and counts cheap (dv < dv_thr) outgoing transfers. If a node
has 0 cheap outgoing transfers to ANY target at EVERY sampled epoch, it is
rigorously intrinsically expensive (not merely epoch-locked).

Diagnostic only. Writes /tmp/ch2_large_epoch_conn_alltargets.json.
"""
import json
import multiprocessing as mp
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = "/tmp/ch2_large_epoch_conn_alltargets.json"

NODES = [739, 343, 753]           # the 3 prior-flagged heavy nodes
N_EPOCHS = 16                     # coarse grid over [0, max_time]
TOF_WINDOW = 30.0
N_STEPS = 120
N_WORKERS = 2

_KT = [None]


def _init(inst):
    _KT[0] = KTTSP(inst)


def _scan(args):
    """For (src, epoch): count cheap outgoing transfers to ALL targets;
    record the cheapest dv seen and the target achieving it."""
    src, ep = args
    kt = _KT[0]
    thr = kt.dv_thr
    cheap = 0
    best_dv = float("inf")
    best_tgt = -1
    for tgt in range(kt.n):
        if tgt == src:
            continue
        tof, dv = find_earliest_transfer(kt, src, tgt, float(ep), thr,
                                         TOF_WINDOW, N_STEPS)
        if tof is not None:
            cheap += 1
            if dv < best_dv:
                best_dv, best_tgt = dv, tgt
    return src, float(ep), cheap, (None if best_tgt < 0 else
                                   {"tgt": best_tgt, "dv": best_dv})


def main():
    t0 = time.time()
    kt = KTTSP(INST)
    epochs = np.linspace(0.0, kt.max_time - 5.0, N_EPOCHS)
    args = [(src, float(ep)) for src in NODES for ep in epochs]
    print(f"[E-591-all] {len(NODES)} nodes x {N_EPOCHS} epochs x "
          f"ALL {kt.n-1} targets", flush=True)
    res = {int(s): {"epochs": [], "cheap_count": [], "best_cheap": []}
           for s in NODES}
    done = 0
    with mp.Pool(N_WORKERS, initializer=_init, initargs=(INST,)) as pool:
        for src, ep, cheap, best in pool.imap_unordered(_scan, args):
            r = res[int(src)]
            r["epochs"].append(ep)
            r["cheap_count"].append(cheap)
            r["best_cheap"].append(best)
            done += 1
            print(f"  [{done}/{len(args)}] node {src} ep={ep:.0f}: "
                  f"cheap_targets={cheap} best={best}", flush=True)
    summary = {}
    for s in NODES:
        r = res[s]
        order = np.argsort(r["epochs"])
        eps = [r["epochs"][i] for i in order]
        cc = [r["cheap_count"][i] for i in order]
        bc = [r["best_cheap"][i] for i in order]
        any_cheap = any(c > 0 for c in cc)
        summary[s] = {
            "epochs": eps, "cheap_count_per_epoch": cc,
            "best_cheap_per_epoch": bc,
            "any_cheap_anywhere": any_cheap,
            "total_cheap_target_hits": int(sum(cc)),
            "verdict": ("epoch-locked (cheap exists somewhere)" if any_cheap
                        else "intrinsically expensive (0 cheap at all epochs)"),
        }
        print(f"[E-591-all] node {s}: {summary[s]['verdict']} "
              f"(total cheap hits {sum(cc)})", flush=True)
    out = {"n_epochs": N_EPOCHS, "tof_window": TOF_WINDOW,
           "n_steps": N_STEPS, "wall_s": round(time.time() - t0, 1),
           "per_node": summary}
    json.dump(out, open(OUT, "w"))
    print(f"[E-591-all] wrote {OUT} ({out['wall_s']}s)", flush=True)


if __name__ == "__main__":
    main()
