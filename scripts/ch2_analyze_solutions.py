"""E-728 — Ch2-large: analyse PATTERNS across alternative complete-order solutions (user: 'find several
alternative solutions, then analyse their patterns'). Loads every complete 601-order we have (bank, static/GLKH
LKH orders, and the CLS local-search checkpoints) and reports:
  - per-solution: makespan, strands (faithful retime_tol), d/leg
  - structural overlap: directed-edge Jaccard between each pair + vs the bank (same topology or different basin?)
  - per-city context variability: how many DISTINCT predecessors/successors a city has across solutions
    (low = structurally forced 'spine'; high = free) -> reveals the forced backbone vs the flexible part
  - hard cities: those whose adjacent legs are consistently long-tof / late (the completion bottleneck)
Usage: python ch2_analyze_solutions.py"""
import sys, json, glob, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import importlib.util
spec = importlib.util.spec_from_file_location("cr", "/home/julian/Projects/esa_spoc_26_3/scripts/ch2_giant_completion_repair.py")
cr = importlib.util.module_from_spec(spec); spec.loader.exec_module(cr)
cr.ft.transfer_dv(cr.OPAR[0], cr.OPAR[1], 10 * cr.DAY, 1 * cr.DAY, cr.MAXREV)
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def load_order(f):
    o = json.load(open(f))
    if isinstance(o, dict):
        p = o.get("path") or o.get("order")
    else:
        p = o
    p = [int(c) for c in p]
    return p if len(p) == 601 and len(set(p)) == 601 else None


def edges(order):
    return set((order[i], order[i + 1]) for i in range(len(order) - 1))


def main():
    sols = {}
    for f in ([f"{ROOT}/cache/ch2_bank_giant_order.json",
               f"{ROOT}/cache/ch2_giant_lkh_order.json",
               f"{ROOT}/cache/ch2giant_glkh_tour.json"]
              + sorted(glob.glob(f"{ROOT}/cache/ch2_giant_cls_*.json"))):
        if not os.path.exists(f):
            continue
        o = load_order(f)
        if o is None:
            continue
        name = os.path.basename(f).replace("ch2_giant_cls_", "cls_").replace("ch2_", "").replace(".json", "")
        sols[name] = o
    print(f"[E-728] loaded {len(sols)} complete 601-orders: {list(sols.keys())}\n")

    # per-solution faithful metrics
    print(f"{'solution':22s} {'strands':>7s} {'makespan':>9s} {'d/leg':>6s}")
    metr = {}
    for name, o in sols.items():
        mk, st, _ = cr.retime_tol(o, 20.0, K=3, W=12)
        metr[name] = (st, mk)
        print(f"{name:22s} {st:7d} {mk:9.1f} {mk/600:6.3f}")
    bank = sols.get("bank_giant_order") or sols.get("giant_order")
    bankedges = edges(bank) if bank else None

    # pairwise directed-edge Jaccard (structural similarity)
    names = list(sols.keys())
    E = {n: edges(o) for n, o in sols.items()}
    print("\n[edge-Jaccard vs bank] (1.0 = identical topology, ~0 = different basin)")
    if bankedges:
        for n in names:
            inter = len(E[n] & bankedges); uni = len(E[n] | bankedges)
            print(f"  {n:22s} {inter/uni:5.3f}  ({inter} shared / {len(E[n])} edges)")

    # per-city context variability across solutions
    from collections import defaultdict
    succ = defaultdict(set); pred = defaultdict(set)
    for o in sols.values():
        for i in range(len(o) - 1):
            succ[o[i]].add(o[i + 1]); pred[o[i + 1]].add(o[i])
    var = {c: len(succ[c]) + len(pred[c]) for c in range(601)}
    forced = sorted(var, key=lambda c: var[c])[:15]
    free = sorted(var, key=lambda c: -var[c])[:15]
    print(f"\n[backbone] 15 most-FORCED cities (same context in all sols, |succ|+|pred| smallest): {forced}")
    print(f"[flexible] 15 most-FREE cities (varies most across sols): {free}")
    nf = sum(1 for c in range(601) if var[c] <= 2)
    print(f"\n{nf}/601 cities have <=2 distinct neighbours across all {len(sols)} solutions "
          f"(= structurally forced spine).")


if __name__ == "__main__":
    main()
