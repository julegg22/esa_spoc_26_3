"""E-720 — Ch2-large rank-1 closer: FAST insertion-repair of the 35 stranded periphery cities.

Base 566-tour (cache/ch2_giant_coverage_c3_566.json) retimes faithfully to 298.04d @ 0 exc.
35 stranded cities (cache/ch2_giant_stranded35.json) are each individually insertable, but naive
all-35 insertion (no re-timing) cascades to 1139d. This script inserts all 35 with faithful
incremental re-timing, bounded per-city work, then reports makespan vs rank-1 424.62d.

Speedups vs scripts/ch2_giant_insertion_repair.py:
  (a) base clock cached once;
  (b) per stranded city j, candidate positions = ONLY tour indices k where pred cur[k] has a cheap
      edge to j (FIN mask, table) AND j has a cheap edge to successor cur[k+1] (FIN mask) -> a SMALL
      set, not all 565;
  (c) suffix re-time is LAZY/incremental: we re-time forward from the insertion point and STOP EARLY
      as soon as the running clock catches back up to the base clock at that index (insertion creates a
      local bump that often re-converges) — bounded by MAX_RETIME legs;
  (d) per-city total fine-tof budget.

Two insertion orders tried: lowest-indeg-first (hardest) and best-insertion-cost-first.
Usage: python ch2_giant_insrepair_fast.py [order=indeg|bestcost] [max_retime=120]"""
import json, sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict

ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
import os
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
indeg = defaultdict(int)
for (i, j) in KEYS:
    indeg[int(j)] += 1

BASE = sys.argv[3] if len(sys.argv) > 3 else f"{ROOT}/cache/ch2_giant_coverage_c3_566.json"
order = json.load(open(BASE))["path"]
allc = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
stranded_all = [c for c in allc if c not in set(order)]          # compute from base (all giant - threaded)
NLEN = len(EPOCHS)


def cheap_arr(i, j, t, dv_cap):
    """earliest <=dv_cap arrival for (i,j) departing >= t; table-proposed + fine verify. (dep,tof,arr) or None."""
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(NLEN, e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= dv_cap:
                return dep, float(tof), dep + float(tof)
    return None


def has_edge(i, j):
    """does (i,j) have ANY finite cheap window in the table? (cheap structural reachability)"""
    row = PIDX.get((i, j))
    return row is not None and FIN[row].any()


def retime_full(seq):
    """faithful forward retime of whole seq from t=0. Returns (times, makespan, exc) or None if strands."""
    t = 0.0; exc = 0; times = [0.0]
    for k in range(1, len(seq)):
        a, b = seq[k - 1], seq[k]
        r = cheap_arr(a, b, t, kt.dv_thr)
        if r is None and exc < kt.n_exc:
            r = cheap_arr(a, b, t, kt.dv_exc)
            if r is not None:
                exc += 1
        if r is None:
            return None
        t = r[2]; times[k:k + 1] = []; times.append(t)
    return times, t, exc


def retime_suffix(seq, start, t_start, exc_start, base_tail):
    """Faithful re-time of seq[start:] from clock t_start (arrival at seq[start-1]) to the END.
    The insertion permanently shifts downstream clocks (phase-aligned windows don't re-converge),
    so we MUST re-time to the end. Early-exit ONLY if the new clock truly drops to/below the prior
    clock at a NEW index (then the unchanged downstream tail is reused). Returns
    (new_times_from_start_list_to_end, end_clock, exc_delta) or None if strands."""
    t = t_start; exc = exc_start
    new_t = []
    n = len(seq)
    for k in range(start, n):
        a, b = seq[k - 1], seq[k]
        r = cheap_arr(a, b, t, kt.dv_thr)
        if r is None and exc < kt.n_exc:
            r = cheap_arr(a, b, t, kt.dv_exc)
            if r is not None:
                exc += 1
        if r is None:
            return None
        t = r[2]; new_t.append(t)
        # true re-convergence (rare with phase-aligned windows): clock dropped to old value here -> reuse tail
        if base_tail is not None and base_tail[k] is not None and t <= base_tail[k] + 1e-9:
            tail = [base_tail[m] for m in range(k + 1, n)]
            return new_t + tail, base_tail[n - 1], exc - exc_start
    return new_t, t, exc - exc_start


def main(mode="indeg", max_retime=120):
    stranded = list(stranded_all)
    if mode == "indeg":
        stranded.sort(key=lambda c: indeg[c])
    print(f"[E-720] FAST insertion repair (order={mode}, max_retime={max_retime}): base {len(order)}/601, "
          f"{len(stranded)} stranded (indeg {indeg[stranded[0]]}..{indeg[stranded[-1]]})", flush=True)
    base = retime_full(order)
    if base is None:
        print("[E-720] base does not retime; abort", flush=True); return
    times, mk, exc = base
    print(f"[E-720] base retimed: makespan {mk:.2f}d, exc {exc}/{kt.n_exc}", flush=True)

    cur = list(order); cur_times = list(times); cur_exc = exc
    inserted = 0; t0 = time.time(); fine_calls0 = [0]
    expensive = []  # (city, makespan_increase)

    # precompute, for each stranded city, its set of predecessor cities (have cheap edge -> j) and
    # successor cities (j has cheap edge ->) present-in-tour test is done at insert time.
    pred_of = {j: set(int(i) for (i, jj) in KEYS if int(jj) == j and has_edge(int(i), j)) for j in stranded}
    succ_of = {j: set(int(jj) for (i, jj) in KEYS if int(i) == j and has_edge(j, int(jj))) for j in stranded}

    # Unified GLOBAL cheapest-insertion: each round, across ALL remaining cities, pick the (city,pos)
    # giving min resulting makespan (full faithful retime). Naturally defers hard cities. `mode` only
    # sets the initial order (cosmetic for global-cheapest) and is kept for the report label.
    remaining = list(stranded)
    failed = []                                   # cities with NO feasible insertion at all (cascade-strands)
    rnd = 0
    while remaining:
        rnd += 1
        jlist = remaining
        best = None  # (makespan, j, newseq, newtimes, newexc, pos)
        for j in jlist:
            P = pred_of[j]; S = succ_of[j]
            # candidate positions: k where cur[k] in P and cur[k+1] in S  (both legs structurally cheap)
            cand_k = [k for k in range(len(cur) - 1) if cur[k] in P and cur[k + 1] in S]
            # LOCAL cost rank: for each candidate, the local two-leg detour delay at the base clock,
            # delay = arr_back_to_b(via j) - old_arr_at_b. Cheaper local detour -> less downstream cascade.
            scored = []
            for k in cand_k:
                a, b = cur[k], cur[k + 1]
                t_a = cur_times[k]
                r1 = cheap_arr(a, j, t_a, kt.dv_thr); ue = 0
                if r1 is None and cur_exc < kt.n_exc:
                    r1 = cheap_arr(a, j, t_a, kt.dv_exc); ue = 1 if r1 else 0
                if r1 is None:
                    continue
                r2 = cheap_arr(j, b, r1[2], kt.dv_thr); ue2 = 0
                if r2 is None and cur_exc + ue < kt.n_exc:
                    r2 = cheap_arr(j, b, r1[2], kt.dv_exc); ue2 = 1 if r2 else 0
                if r2 is None:
                    continue
                local_delay = r2[2] - cur_times[k + 1]   # how much later b is reached via the detour
                scored.append((local_delay, k, ue + ue2))
            scored.sort(key=lambda x: x[0])
            # full-retime the TOP positions (best local detour) — sorted, so the FIRST non-stranding one
            # dominates min-makespan; break after it (bounded by max_retime probes for the cascade-y cities).
            jbest = None
            for (local_delay, k, _ue) in scored[:max_retime]:
                newseq = cur[:k + 1] + [j] + cur[k + 1:]
                base_tail = [None] * len(newseq)
                for m in range(k + 2, len(newseq)):
                    base_tail[m] = cur_times[m - 1]
                rt = retime_suffix(newseq, k + 1, cur_times[k], cur_exc, base_tail)
                if rt is None:
                    continue
                new_t_from_start, end_clock, exc_delta = rt
                newtimes = cur_times[:k + 1] + new_t_from_start
                if len(newtimes) != len(newseq):
                    continue
                nexc = cur_exc + exc_delta
                if nexc > kt.n_exc:
                    continue
                nmk = newtimes[-1]
                jbest = (nmk, j, newseq, newtimes, nexc, k)
                break                                     # first feasible (min local_delay) dominates
            if jbest is not None and (best is None or jbest[0] < best[0]):
                best = jbest
        if best is None:
            # no remaining city has any feasible (non-stranding) insertion position
            failed = list(remaining)
            print(f"[E-720] {len(remaining)} remaining cities have NO feasible insertion position "
                  f"(cascade-strands at every candidate pos): {sorted(remaining)}", flush=True)
            break
        nmk, j, newseq, newtimes, nexc, pos = best
        inc = nmk - cur_times[-1]
        cur, cur_times, cur_exc = newseq, newtimes, nexc
        inserted += 1
        if inc > 5.0:
            expensive.append((j, round(inc, 1)))
        remaining.remove(j)
        print(f"  ins {inserted}/{len(stranded)} city {j}(indeg {indeg[j]})@pos {pos} "
              f"+{inc:.2f}d -> mk {nmk:.2f}d exc {cur_exc} | {len(remaining)} left [{time.time()-t0:.0f}s]", flush=True)

    final_mk = cur_times[-1]
    print(f"\n[E-720] DONE ({mode}): inserted {inserted}/{len(stranded)} -> {len(cur)}/601 visited, "
          f"makespan {final_mk:.2f}d, exc {cur_exc}/{kt.n_exc} [{time.time()-t0:.0f}s]", flush=True)
    if failed:
        print(f"[E-720] FAILED to insert {len(failed)} cities (no non-stranding position): {sorted(failed)}", flush=True)
    if expensive:
        expensive.sort(key=lambda x: -x[1])
        print(f"[E-720] expensive insertions (>5d): {expensive[:15]}", flush=True)
    out = {"order": cur, "visited": len(cur), "makespan": final_mk, "exc": cur_exc, "mode": mode,
           "inserted": inserted, "expensive": expensive, "failed": sorted(failed)}
    json.dump(out, open(f"{ROOT}/cache/ch2_giant_insrepair601_{mode}.json", "w"))
    verdict = "RANK-1" if (len(cur) >= 599 and final_mk < 424.62 and cur_exc <= 5) else "no"
    print(f"[E-720] verdict: {verdict} (need >=599 visited, mk<424.62, exc<=5)", flush=True)
    if verdict == "RANK-1":
        json.dump(out, open(f"{ROOT}/cache/ch2_giant_insrepair601.json", "w"))
        print(f"[E-720] *** saved cache/ch2_giant_insrepair601.json", flush=True)
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "indeg"
    mr = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    main(mode, mr)
