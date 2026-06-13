"""E-587 — Ch2 LARGE per-component LKH (elkai) on the epoch-aware fine grid.

Novel lever: replace E-562b's OR-Tools GLS per-piece solver with LKH
(Lin-Kernighan-Helsgaun via the `elkai` wrapper) inside the SAME
sequential epoch-aware iteration loop:
  - decompose the banked 1051-perm into its 6 component-pure open-path
    pieces (split at the 5 exc bridges); each piece has FIXED bridge
    endpoints (start,end);
  - build an epoch-aware cost matrix for the piece on the SAME grid the
    chrono walk uses (find_earliest_transfer, dv_thr=cheap, tof_window/
    n_steps from WALK), with the departure epoch of each node taken from
    the previous chrono walk;
  - re-solve the open path with LKH (virtual-depot encoding for fixed
    start/end), forbidding non-cheap edges (BIG) so the piece stays a
    0-big-jump cheap-only Hamiltonian path;
  - re-walk the FULL 1051-perm after each piece so downstream pieces see
    fresh (earlier) epochs; iterate to convergence.

GUARDED: writes any strictly-better feasible 1051-perm to /tmp ONLY.
Banks NOTHING.  Validated with walk_perm_chrono AND kt.fitness.
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import elkai

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = os.environ.get("E587_OUT", "/tmp/ch2_large_cand.json")
CURRENT_BANK = 942.0744268445161
R1 = 424.62

BIG = 10_000_000          # forbidden (non-cheap) edge
SCALE = 1000.0            # tof(days) -> int cost
TOF_WINDOW = 40.0
N_STEPS = 2400            # SAME grid as the verifying walk (E-045 fine)
LKH_RUNS = int(os.environ.get("E587_RUNS", "8"))
N_ITERS = int(os.environ.get("E587_ITERS", "8"))
STOP_DELTA = float(os.environ.get("E587_STOP", "0.05"))

# Walk params identical to the banked walk (so epochs reproduce exactly).
WALK = dict(tof_window=40.0, n_steps=2400, wait_steps=8, wait_dt=0.25)


def walk_stats(kt, perm):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, perm, **WALK)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return dict(times=times, tofs=tofs, dvs=dvs, x=x, mk=float(fit[0]),
                feas=bool(kt.is_feasible(fit)), exc=exc,
                viols=list(fit[1:]), ok=True)


_KT = None


def _init_worker(inst):
    global _KT
    _KT = KTTSP(inst)


def _row_cost(args):
    """Compute one row a of the epoch-aware cheap cost matrix."""
    a, i, t_i, nodes = args
    m = len(nodes)
    row = np.full(m, BIG, dtype=np.int64)
    nf = 0
    for b in range(m):
        if a == b:
            row[b] = 0
            continue
        tof, dv = find_earliest_transfer(
            _KT, i, nodes[b], t_i, _KT.dv_thr, TOF_WINDOW, N_STEPS)
        if tof is not None:
            row[b] = int(round(tof * SCALE))
        else:
            nf += 1
    return a, row, nf


_POOL = None


def build_cost_epoch(kt, nodes, epoch):
    """Epoch-aware cheap-only cost over `nodes`, built in parallel.
    epoch[gid] = departure epoch in current chrono walk. Forbidden -> BIG."""
    m = len(nodes)
    C = np.full((m, m), BIG, dtype=np.int64)
    tasks = [(a, nodes[a], float(epoch[nodes[a]]), nodes) for a in range(m)]
    n_forbid = 0
    for a, row, nf in _POOL.map(_row_cost, tasks, chunksize=4):
        C[a] = row
        n_forbid += nf
    return C, n_forbid


def solve_open_path_lkh(C, s, e, runs):
    """Open Hamiltonian path over indices 0..m-1 with FIXED start s, end e,
    minimizing sum of C. Virtual-depot encoding -> closed ATSP -> LKH.
    Returns local-index order (length m) starting at s, ending at e, or None
    if LKH used any forbidden (BIG) edge."""
    m = C.shape[0]
    dep = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    # depot closes the path: e -> depot -> s only, both 0 cost.
    D[dep, :] = BIG
    D[:, dep] = BIG
    D[dep, dep] = 0
    D[dep, s] = 0          # depot -> start
    D[e, dep] = 0          # end -> depot
    np.fill_diagonal(D, 0)
    tour = elkai.DistanceMatrix(D.tolist()).solve_tsp(runs=runs)
    # tour is closed (last==first). Strip the closing repeat.
    tour = tour[:-1]
    # rotate so depot leads, then drop it -> order from s..e
    di = tour.index(dep)
    rot = tour[di + 1:] + tour[:di]
    if rot[0] != s or rot[-1] != e or len(rot) != m or len(set(rot)) != m:
        return None, None
    # count big jumps actually used along rot
    big = 0
    for k in range(1, m):
        if C[rot[k - 1], rot[k]] >= BIG:
            big += 1
    return rot, big


def main():
    global _POOL
    kt = KTTSP(INST)
    n = kt.n
    _POOL = ProcessPoolExecutor(max_workers=2, initializer=_init_worker,
                                initargs=(INST,))
    adj = np.load("/tmp/ch2_e533_large_adj.npz")
    labels = adj["labels"]

    bank = json.load(open(BANK))[0]["decisionVector"]
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    w0 = walk_stats(kt, perm)
    assert w0 and w0["feas"], "bank not walkable"
    print(f"[BASE] mk={w0['mk']:.4f} feas={w0['feas']} exc={w0['exc']} "
          f"viols={w0['viols']} (bank {CURRENT_BANK}, r1 {R1})", flush=True)

    # exc-bridge split points from the walk's dv vector
    dvs = np.array(w0["dvs"])
    exc_legs = np.where(dvs > kt.dv_thr + 1e-9)[0]
    splits = [0] + [int(e) + 1 for e in exc_legs] + [len(perm)]
    pieces = [list(perm[splits[i]:splits[i + 1]])
              for i in range(len(splits) - 1)]
    # endpoints are fixed (bridge endpoints): (start,end) per piece
    endpoints = [(p[0], p[-1]) for p in pieces]
    print(f"[STRUCT] {len(pieces)} pieces lens="
          f"{[len(p) for p in pieces]} "
          f"comps={[int(labels[p[0]]) for p in pieces]}", flush=True)

    best_mk = w0["mk"]
    best_x = w0["x"]
    cur_pieces = [list(p) for p in pieces]
    prev_mk = w0["mk"]
    t_start = time.time()

    for it in range(N_ITERS):
        print(f"\n===== LKH EPOCH-AWARE ITER {it} "
              f"({time.time()-t_start:.0f}s) =====", flush=True)
        full = [g for p in cur_pieces for g in p]
        w = walk_stats(kt, full)
        mk_cur = w["mk"]
        epoch = {full[k]: w["times"][k] for k in range(len(w["times"]))}
        epoch[full[-1]] = w["times"][-1]

        for pi in range(len(cur_pieces)):
            nodes = cur_pieces[pi]
            s_gid, e_gid = endpoints[pi]
            si = nodes.index(s_gid)
            ei = nodes.index(e_gid)
            tb = time.time()
            C, nforb = build_cost_epoch(kt, nodes, epoch)
            order_idx, big = solve_open_path_lkh(C, si, ei, LKH_RUNS)
            if order_idx is None:
                print(f"  [p{pi}] LKH endpoint/perm fail — keep prev",
                      flush=True)
                continue
            new_nodes = [int(nodes[k]) for k in order_idx]
            if big > 0:
                print(f"  [p{pi}] LKH used {big} forbidden edges — keep prev",
                      flush=True)
                continue
            # GUARDED ACCEPT: matrix proposes, chrono walk disposes. Only
            # keep the reorder if the TRUE makespan does not regress.
            cur_pieces[pi] = new_nodes
            full = [g for p in cur_pieces for g in p]
            w = walk_stats(kt, full)
            ok = (w is not None and w["feas"] and w["mk"] <= mk_cur + 1e-6)
            if not ok:
                mk_new = None if w is None else round(w["mk"], 4)
                cur_pieces[pi] = nodes
                full = [g for p in cur_pieces for g in p]
                w = walk_stats(kt, full)
                print(f"  [p{pi}] n={len(nodes)} forbid={nforb} REJECT "
                      f"(walk mk={mk_new} vs cur {mk_cur:.4f}) "
                      f"({time.time()-tb:.0f}s)", flush=True)
            else:
                mk_cur = w["mk"]
                epoch = {full[k]: w["times"][k]
                         for k in range(len(w["times"]))}
                epoch[full[-1]] = w["times"][-1]
                print(f"  [p{pi}] n={len(nodes)} forbid={nforb} ACCEPT -> "
                      f"mk={w['mk']:.4f} feas={w['feas']} exc={w['exc']} "
                      f"({time.time()-tb:.0f}s)", flush=True)

        full = [g for p in cur_pieces for g in p]
        assert len(full) == n and len(set(full)) == n, "bad perm"
        w = walk_stats(kt, full)
        if w is None:
            print(f"[iter {it}] walk failed — stop", flush=True)
            break
        tof = np.array(w["tofs"])
        print(f"[iter {it}] mk={w['mk']:.4f} feas={w['feas']} exc={w['exc']} "
              f"viols={w['viols']} tofsum={tof.sum():.1f} "
              f">3d={int((tof>3).sum())}", flush=True)

        if w["feas"] and w["mk"] < best_mk:
            best_mk = w["mk"]
            best_x = w["x"]
            json.dump([{"decisionVector": best_x, "problem": "large",
                        "challenge": CHALLENGE}], open(OUT, "w"))
            print(f"[iter {it}] NEW BEST mk={best_mk:.4f} -> {OUT}",
                  flush=True)

        improve = prev_mk - w["mk"]
        print(f"[iter {it}] improvement vs prev = {improve:.4f}d", flush=True)
        prev_mk = w["mk"]
        if abs(improve) < STOP_DELTA:
            print(f"[iter {it}] |improve| < {STOP_DELTA} — converged.",
                  flush=True)
            break

    print(f"\n[FINAL] best_mk={best_mk:.4f} (bank {CURRENT_BANK}, r1 {R1})",
          flush=True)
    if best_mk < CURRENT_BANK - 1e-4:
        # independent re-validate
        fit = kt.fitness(best_x)
        feas = bool(kt.is_feasible(fit))
        perm = [int(round(v)) for v in best_x[2 * (n - 1):]]
        covered = len(set(perm)) == n
        print(f"[REVAL] mk={fit[0]:.4f} feas={feas} viols={list(fit[1:])} "
              f"covered={covered} -> WROTE {OUT}", flush=True)
    else:
        print("[FINAL] did NOT beat bank — /tmp candidate (if any) is the "
              "fine-walk of an equal-or-worse perm; bank unchanged.",
              flush=True)


if __name__ == "__main__":
    main()
