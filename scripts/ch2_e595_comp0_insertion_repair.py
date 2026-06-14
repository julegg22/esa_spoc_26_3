"""E-595 TD-aware insertion-repair for Ch2 LARGE comp0 (close the beam's tail).

Established (E-592/593/594, this session): comp0 (601-node giant of the n=1051
KTTSP) is the entire Ch2-large r2->r1 difficulty. A plain B=10 beam threads
571/601 at ~0.48 d/leg but is APPEND-ONLY and strands the last ~30 low-degree
(scarce, internal-deg<=20) nodes; every "visit-scarce-early" variant (Warnsdorff
in generation, stranding penalty in score, diversity-blend) REGRESSED. The wall
is therefore an INSERTION problem, not a construction-ORDER problem: the deep
571-path exists, the 30 leftover just need to be threaded INTO it.

The blocker for insertion in a TIME-DEPENDENT tour is the epoch-shift trap: a
mid-path insert delays arrival at every downstream node, so the whole suffix must
be re-validated at shifted epochs (this is exactly why elkai/LKH on a fixed-epoch
cost matrix failed, E-587). This engine confronts that head-on: for each leftover
u it considers ONLY insertion slots where both neighbours are cheap-adjacent to u
(few, since u is scarce), tries append-at-end (no suffix re-walk), and for each
candidate slot RE-WALKS the suffix with find_earliest_transfer at the shifted
epochs, accepting the min-makespan slot that keeps the ENTIRE suffix feasible.
Greedy scarcest-first so the hardest nodes get the most slots.

Binary question -> does TD insertion thread all 30 leftover into the 571-path
(=> COMPLETE comp0)? At what makespan? COMPLETE comp0 (+3 greedy smalls + 5 exc
bridges) feasible < r1=424.62 would be RANK 1 (+1.778). Read-only; banks NOTHING;
dumps the completed/best comp0 path to /tmp for a separate guarded assemble step.

Usage: python ch2_e595_comp0_insertion_repair.py [partial_json] [WIN] [STEPS]
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ = "/tmp/ch2_e533_large_adj.npz"
WIN = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 80


def _find(p, i):
    r = i
    while p[r] != r:
        r = p[r]
    while p[i] != r:
        p[i], i = r, p[i]
    return r


def components(cheap, n):
    p = np.arange(n)
    rows, cols = np.where(cheap)
    for a, b in zip(rows, cols):
        ra, rb = _find(p, int(a)), _find(p, int(b))
        if ra != rb:
            p[rb] = ra
    roots = np.array([_find(p, i) for i in range(n)])
    _, comp = np.unique(roots, return_inverse=True)
    return comp


def leg(kt, i, j, t):
    """Earliest cheap TD tof for i->j departing at epoch t (None if infeasible)."""
    tof, _dv = find_earliest_transfer(kt, int(i), int(j), float(t),
                                      kt.dv_thr, WIN, STEPS)
    return tof


def walk_epochs(kt, path):
    """Arrival epoch at each node of `path` (t[0]=0). Returns (t, ok)."""
    t = [0.0]
    for k in range(len(path) - 1):
        tof = leg(kt, path[k], path[k + 1], t[k])
        if tof is None:
            return t, False
        t.append(t[k] + tof)
    return t, True


def suffix_feasible(kt, path, t, p, u, neigh_set):
    """Try inserting u between path[p] and path[p+1]; re-walk the suffix at
    shifted epochs. Returns (new_t_full, makespan) if the WHOLE suffix stays
    feasible, else None. p == len(path)-1 means append-at-end (no suffix)."""
    tof1 = leg(kt, path[p], u, t[p])
    if tof1 is None:
        return None
    t_u = t[p] + tof1
    if p == len(path) - 1:                      # append at end
        return t[:p + 1] + [t_u], t_u
    tof2 = leg(kt, u, path[p + 1], t_u)
    if tof2 is None:
        return None
    new_t = t[:p + 1] + [t_u]
    tcur = t_u + tof2
    new_t.append(tcur)
    for k in range(p + 1, len(path) - 1):
        tof = leg(kt, path[k], path[k + 1], tcur)
        if tof is None:
            return None
        tcur += tof
        new_t.append(tcur)
    return new_t, tcur


def main():
    partial = (sys.argv[1] if len(sys.argv) > 1
               else "/tmp/ch2_e594_comp3_partial_B10.json")
    if not os.path.exists(partial):
        partial = "/tmp/ch2_e594_comp3_partial.json"
    kt = KTTSP(INST)
    n = kt.n
    cheap = np.load(ADJ)["cheap"]
    comp = components(cheap, n)
    pj = json.load(open(partial))
    target_comp = int(pj["comp"])
    nodes = np.where(comp == target_comp)[0]
    cset = set(int(x) for x in nodes)
    neigh_in = {int(i): set(int(j) for j in np.where(cheap[i])[0]
                            if comp[j] == target_comp) for i in nodes}

    path = [int(x) for x in pj["order"]]
    leftover = [int(x) for x in pj.get("leftover", sorted(cset - set(path)))]
    deg = {u: len(neigh_in[u]) for u in leftover}
    leftover.sort(key=lambda u: deg[u])          # scarcest first
    t, ok = walk_epochs(kt, path)
    print(f"[E-595] partial={os.path.basename(partial)} comp={target_comp} "
          f"path={len(path)}/{len(cset)} leftover={len(leftover)} "
          f"start_mk={t[-1]:.2f}d walk_ok={ok} WIN={WIN} STEPS={STEPS} "
          f"leftover_deg(min/med/max)={min(deg.values())}/"
          f"{int(np.median(list(deg.values())))}/{max(deg.values())}", flush=True)
    if not ok:
        print("[ABORT] loaded partial path is itself infeasible at WIN/STEPS — "
              "regenerate with matching beam params.", flush=True)
        return

    t0 = time.time()
    inserted, failed = 0, []
    for u in leftover:
        nu = neigh_in[u]
        # candidate slots: append-at-end + positions where BOTH path[p] and
        # path[p+1] are cheap-adjacent to u (so both legs CAN be cheap).
        cands = [len(path) - 1] if path[-1] in nu else []
        for p in range(len(path) - 1):
            if path[p] in nu and path[p + 1] in nu:
                cands.append(p)
        best = None                              # (makespan, p, new_t)
        for p in cands:
            r = suffix_feasible(kt, path, t, p, u, nu)
            if r is None:
                continue
            new_t, mk = r
            if best is None or mk < best[0]:
                best = (mk, p, new_t)
        if best is None:
            failed.append(u)
            continue
        mk, p, new_t = best
        path = path[:p + 1] + [u] + path[p + 1:]
        t = new_t
        inserted += 1
        if inserted % 5 == 0 or len(cands) == 0:
            print(f"  inserted={inserted}/{len(leftover)} last_u={u} "
                  f"(deg {deg[u]}, {len(cands)} slots) at p={p} mk={mk:.2f}d "
                  f"path={len(path)} t={time.time()-t0:.0f}s", flush=True)

    complete = (len(path) == len(cset))
    print(f"[RESULT] inserted={inserted}/{len(leftover)} "
          f"path={len(path)}/{len(cset)} {'COMPLETE' if complete else 'PARTIAL'} "
          f"mk={t[-1]:.2f}d ({t[-1]/max(1,len(path)-1):.3f} d/leg) "
          f"failed={len(failed)} ({time.time()-t0:.0f}s)", flush=True)
    out = (f"/tmp/ch2_e595_comp{target_comp}_"
           f"{'complete' if complete else 'partial'}.json")
    json.dump({"comp": target_comp, "order": [int(x) for x in path],
               "mk": float(t[-1]), "complete": complete,
               "failed": [int(x) for x in failed],
               "target": int(len(cset))}, open(out, "w"))
    if complete:
        print(f"[FINAL] comp{target_comp} COMPLETE via insertion-repair -> {out}. "
              f"GO assemble (+3 greedy smalls +5 exc bridges) vs r1=424.62.",
              flush=True)
    else:
        print(f"[FINAL] {len(failed)} nodes still un-insertable -> {out}. "
              f"Next: backtracking-beam or relax WIN for the failed set.",
              flush=True)


if __name__ == "__main__":
    main()
