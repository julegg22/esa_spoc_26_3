"""E-579 — Ch2 LARGE: per-leg slack + ring-membership diagnostic.

Decisive diagnostic, NOT a search. Decomposes the bank's 624d gap to r1
into causes, leg by leg. For each realized bank leg (cur -> nxt at the
bank's departure epoch t_dep):

  realized_tof  = bank tof for this leg
  best_unvis    = min find_earliest_transfer(cur, j, t_dep) over ALL
                  still-unvisited j (cheap only, dv<=dv_thr)
  slack         = realized_tof - best_unvis  (>0 => we passed up a
                  cheaper hop; the realized target was NOT the cheapest
                  reachable node)

Also tags each node with (shell, plane) ring membership so we can see
whether long legs are intra-ring phase-misses or inter-ring bridges.

If most of the 624d excess is "slack" against still-unvisited nodes ->
the gap is greedy-myopia / ordering (a better global construction
recovers it). If realized ~= best_unvis on the long legs -> those long
legs were forced (endgame, candidate set exhausted) and r1 needs a
fundamentally different visiting strategy.

Read-only. Prints summary + writes /tmp/ch2_e579_legslack.json. Banks
nothing.
"""
import json
import multiprocessing as mp
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
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = "/tmp/ch2_e579_legslack.json"

TOF_WINDOW = float(os.environ.get("E579_TOFWIN", "12.0"))
N_STEPS = int(os.environ.get("E579_NSTEPS", "120"))
WORKERS = int(os.environ.get("E579_WORKERS", "4"))
# To bound runtime: for each leg, probe at most N_CAND nearest-by-a/plane
# unvisited candidates instead of all ~1000. The ring structure means the
# cheapest reachable node is essentially always same-shell/same-plane, so
# a candidate set built from shell+plane neighbours is faithful & ~50x
# cheaper. We ALSO include a random sample of other unvisited nodes as a
# control.
N_CAND = int(os.environ.get("E579_NCAND", "60"))
N_CTRL = int(os.environ.get("E579_NCTRL", "20"))

_KT = [None]


def _init(inst):
    _KT[0] = KTTSP(inst)


def _ring_labels(kt):
    a = kt.opar[:, 0] / 1000.0
    inc = (np.degrees(kt.opar[:, 2])) % 360.0
    shell = np.where(a < 8000, 0, 1)
    # plane bucket at 15-deg granularity; fold 360->0
    plane = (np.round(inc / 15.0).astype(int) * 15) % 360
    return shell, plane


def _leg_probe(args):
    """For leg index k: cur, t_dep, realized_tof, cand_list ->
    best feasible cheap tof over cand_list and its argmin node."""
    k, cur, t_dep, realized_tof, cands = args
    kt = _KT[0]
    best = np.inf
    bj = -1
    for j in cands:
        tof, dv = find_earliest_transfer(
            kt, int(cur), int(j), float(t_dep), kt.dv_thr, TOF_WINDOW, N_STEPS)
        if tof is not None and tof < best:
            best = tof
            bj = int(j)
    return k, (best if np.isfinite(best) else np.nan), bj


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    times = np.array(bank[:n - 1], dtype=float)
    tofs = np.array(bank[n - 1:2 * (n - 1)], dtype=float)
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    fit = kt.fitness(bank)
    mk = float(fit[0])
    print(f"[E-579] bank mk={mk:.2f}d feas={bool(kt.is_feasible(fit))} "
          f"legs={len(tofs)} tof_sum={tofs.sum():.1f}", flush=True)

    shell, plane = _ring_labels(kt)
    # precompute per-(shell,plane) member lists
    groups = {}
    for idx in range(n):
        groups.setdefault((int(shell[idx]), int(plane[idx])), []).append(idx)

    rng = np.random.default_rng(0)
    visited = set()
    tasks = []
    for k in range(len(tofs)):
        cur = perm[k]
        nxt = perm[k + 1]
        t_dep = float(times[k])
        visited.add(cur)
        # candidate set: unvisited members of cur's own ring + adjacent
        # planes (same shell), capped; plus random control sample.
        sshell = int(shell[cur])
        cand = []
        for (sh, pl), mem in groups.items():
            if sh != sshell:
                continue
            for m in mem:
                if m not in visited and m != cur:
                    cand.append(m)
        cand = list(set(cand))
        if len(cand) > N_CAND:
            cand = list(rng.choice(cand, size=N_CAND, replace=False))
        # control: random unvisited from anywhere
        allun = [m for m in range(n) if m not in visited and m != cur]
        if allun:
            ctrl = list(rng.choice(allun, size=min(N_CTRL, len(allun)),
                                   replace=False))
        else:
            ctrl = []
        # ensure realized target is in the set so slack>=0 by construction
        cset = list(set(cand + ctrl + [nxt]))
        tasks.append((k, cur, t_dep, float(tofs[k]), cset))

    print(f"[E-579] probing {len(tasks)} legs, "
          f"cand~{N_CAND}+ctrl{N_CTRL}, workers={WORKERS}", flush=True)

    best_tof = np.full(len(tofs), np.nan)
    best_j = np.full(len(tofs), -1, dtype=int)
    t0 = time.time()
    with mp.Pool(WORKERS, initializer=_init, initargs=(INST,)) as p:
        done = 0
        for k, bt, bj in p.imap_unordered(_leg_probe, tasks, chunksize=4):
            best_tof[k] = bt
            best_j[k] = bj
            done += 1
            if done % 100 == 0:
                print(f"  [E-579] {done}/{len(tasks)} legs "
                      f"({time.time()-t0:.0f}s)", flush=True)

    slack = tofs - best_tof  # >0 => cheaper hop existed to some unvisited
    valid = ~np.isnan(best_tof)
    # classify legs
    realized_same_ring = np.array([
        shell[perm[k]] == shell[perm[k + 1]] and
        plane[perm[k]] == plane[perm[k + 1]]
        for k in range(len(tofs))])
    bridge = ~realized_same_ring

    print("\n==== E-579 RESULTS ====", flush=True)
    print(f"legs with a probe result: {int(valid.sum())}/{len(tofs)}",
          flush=True)
    pos = valid & (slack > 0.05)
    print(f"total realized tof_sum = {tofs.sum():.1f}d", flush=True)
    print(f"sum(best_unvis over probed) = {np.nansum(best_tof):.1f}d",
          flush=True)
    print(f"RECOVERABLE SLACK (sum max(0,slack)) = "
          f"{np.nansum(np.clip(slack,0,None)):.1f}d "
          f"over {int(pos.sum())} legs", flush=True)
    for thr in (0.5, 1.0, 2.0):
        m = valid & (tofs > thr)
        sm = valid & (tofs > thr) & (slack > 0.05)
        print(f"  long legs >{thr}d: {int(m.sum())}, of which had a cheaper "
              f"unvisited option: {int(sm.sum())} "
              f"(recoverable {np.nansum(np.clip(slack[sm],0,None)):.1f}d)",
              flush=True)
    print(f"\nbridge legs (cross-ring): {int(bridge.sum())} "
          f"tof_sum={tofs[bridge].sum():.1f}d", flush=True)
    print(f"intra-ring legs: {int(realized_same_ring.sum())} "
          f"tof_sum={tofs[realized_same_ring].sum():.1f}d", flush=True)
    # long intra-ring legs = phase-miss signature
    pm = realized_same_ring & (tofs > 0.5)
    print(f"intra-ring legs >0.5d (PHASE-MISS candidates): {int(pm.sum())} "
          f"excess_over_0.5={float((tofs[pm]-0.5).sum()):.1f}d", flush=True)

    json.dump({
        "mk": mk, "tof_sum": float(tofs.sum()),
        "recoverable_slack": float(np.nansum(np.clip(slack, 0, None))),
        "bridge_legs": int(bridge.sum()),
        "bridge_tof": float(tofs[bridge].sum()),
        "intra_ring_legs": int(realized_same_ring.sum()),
        "intra_ring_tof": float(tofs[realized_same_ring].sum()),
        "phasemiss_legs": int(pm.sum()),
        "phasemiss_excess": float((tofs[pm] - 0.5).sum()),
        "best_tof": best_tof.tolist(),
        "realized_tof": tofs.tolist(),
    }, open(OUT, "w"))
    print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
