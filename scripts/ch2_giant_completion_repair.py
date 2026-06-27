"""E-727 — Ch2-large rank-1: faithful insertion-repair completion (re-try-queue #1, fixed tools).

The re-try queue (A-2026-06-27) flags the LNS/insertion-repair "cascade" verdict (E-721) as a TOOL-ARTIFACT:
the 34->220 cascade was largely the BROKEN evaluator (T1 sparse table + T2 long-tof-blind retimer) failing to
find windows that exist. This re-runs insertion-repair with the FIXED tools:
  - combined window source: faithful epoch-dense short-tof (E-726d) UNION dense1d long-tof (0-950) -> a leg can
    use a long tof when phasing demands (pure short-tof caps ~191 structurally; 17% of bank legs need >1.3d).
  - MID-TOUR insertion (the thing a forward beam can't do): place a stranded city between two existing legs,
    allowing WAIT (re-phasing) at the insertion point.
Seed = a GRASP faithful partial (already feasible). Question: does non-greedy repair on the fixed evaluator
complete past the ~331/575 cap, and at what makespan? Honest test, instrumented + checkpointed.

Usage: python ch2_giant_completion_repair.py [seed_json=grasp_best_k] [maxwait=40] [tag=k]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_fast_transfer as ft
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MAXREV = kt.max_revs; MINTOF = kt.min_tof; DAY = 86400.0

# ---- combined window source: faithful short-tof (epoch-dense) UNION dense1d (full 0-950, incl long-tof) -------
d1 = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d1["epochs"]; KEYS = d1["keys"]; VALS = d1["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
cities = sorted(set(int(i) for i in set(KEYS[:, 0]) | set(KEYS[:, 1]))); NG = len(cities)
_FW = np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item()
print(f"[E-727] dense1d {len(PIDX)} edges (0-{EPOCHS[-1]:.0f}d), faithful short-tof {len(_FW)} edges, n={NG}",
      flush=True)
OUTADJ = defaultdict(set); INADJ = defaultdict(set)
for (i, j) in PIDX:
    if FIN[PIDX[(i, j)]].any():
        OUTADJ[i].add(j); INADJ[j].add(i)
for (i, j) in _FW:
    OUTADJ[i].add(j); INADJ[j].add(i)


def CT(i, j, dep, tof):
    return ft.transfer_dv(OPAR[i], OPAR[j], dep * DAY, tof * DAY, MAXREV)


def retime_tol(order, maxwait, K=3, W=12, SP=30.0):
    """TOLERANT W-beam retime over a COMPLETE order: a leg with no cheap window does NOT stop the walk — it
    penalty-carries the clock (+SP) and increments a STRAND counter. Returns (makespan, n_strands). This is the
    objective for complete-order local search: never drop a city; drive n_strands -> 0 instead. (The constructive
    methods all DROP cities and strand; this one keeps all 601 and penalizes infeasible legs = robust by design.)"""
    states = [0.0]; strands = 0; slegs = []
    for p in range(len(order) - 1):
        i, j = order[p], order[p + 1]
        nxt = []
        for t in states:
            nxt.extend(windows_k(i, j, t, K, maxwait))
        if not nxt:
            states = [t + SP for t in states]; strands += 1; slegs.append(p); continue
        states = sorted(set(round(x, 4) for x in nxt))[:W]
    return states[0], strands, slegs


def retime_full(order, maxwait, K=3, W=12, SP=30.0):
    """retime_tol + per-position CACHE: hist[p] = beam states upon ARRIVING at position p (after legs 0..p-1);
    cum[p] = strands incurred in legs 0..p-1. Lets a later move that only changes the order from position q
    onward be re-timed incrementally (retime_inc) instead of from scratch. Called on each ACCEPTED order."""
    states = [0.0]; strands = 0; slegs = []
    hist = [list(states)]; cum = [0]
    for p in range(len(order) - 1):
        i, j = order[p], order[p + 1]
        nxt = []
        for t in states:
            nxt.extend(windows_k(i, j, t, K, maxwait))
        if not nxt:
            states = [t + SP for t in states]; strands += 1; slegs.append(p)
        else:
            states = sorted(set(round(x, 4) for x in nxt))[:W]
        hist.append(list(states)); cum.append(strands)
    return states[0], strands, slegs, hist, cum


def retime_inc(order, q, states0, strands0, maxwait, K=3, W=12, SP=30.0):
    """incremental re-time of order from position q, reusing cached arriving-states (states0) and prefix strand
    count (strands0) at q. Only legs q..n-2 are recomputed -> candidate eval cost ~ (n-q)/n of a full retime.
    Returns (makespan, total_strands). Prefix [0,q) must be identical to the order that produced (states0,strands0)."""
    states = list(states0); strands = strands0
    for p in range(q, len(order) - 1):
        i, j = order[p], order[p + 1]
        nxt = []
        for t in states:
            nxt.extend(windows_k(i, j, t, K, maxwait))
        if not nxt:
            states = [t + SP for t in states]; strands += 1; continue
        states = sorted(set(round(x, 4) for x in nxt))[:W]
    return states[0], strands


def windows_k(i, j, t, K, maxwait):
    """up to K feasible arrival times on i->j departing in [t, t+maxwait], at distinct cheap phases (ascending
    arrival). Combined source: faithful short-tof (epoch-dense) + dense1d (long-tof), CT-verified on dense1d."""
    out = []
    fw = _FW.get((i, j))
    if fw is not None:
        deps, tofs = fw
        q = np.searchsorted(deps, t)
        e = q
        while e < len(deps) and deps[e] <= t + maxwait and len(out) < K:
            out.append(float(deps[e] + tofs[e])); e += 1
    row = PIDX.get((i, j))
    if row is not None and len(out) < K:
        e0 = np.searchsorted(EPOCHS, t)
        for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + int(maxwait) + 2)):
            if len(out) >= K:
                break
            if not FIN[row, e]:
                continue
            dep = max(t, float(EPOCHS[e]))
            if dep > t + maxwait:
                break
            h = float(VALS[row, e])
            for tof in np.arange(max(MINTOF, h - 0.03), h + 0.03, 0.001):
                if CT(i, j, dep, float(tof)) <= THR:
                    out.append(dep + float(tof)); break
    return sorted(set(round(x, 4) for x in out))[:K]


def earliest(i, j, t, maxwait):
    w = windows_k(i, j, t, 1, maxwait)
    return w[0] if w else None


def retime(order, maxwait, K=3, W=16, stop_on_strand=True):
    """W>1 window-branching forward retime (the timebeam, fast combined lookup; W=1 greedy strands feasible
    orders). Returns (per-position min-arrival array, strand_index or None). arr[p] = min arrival at order[p]
    across surviving beam states (a valid lower bound for insertion ranking)."""
    states = [0.0]                                              # arrival times of beam states at current city
    arr = [0.0]
    for p in range(len(order) - 1):
        i, j = order[p], order[p + 1]
        nxt = []
        for t in states:
            nxt.extend(windows_k(i, j, t, K, maxwait))
        if not nxt:
            return arr, p
        nxt = sorted(set(round(x, 4) for x in nxt))[:W]
        states = nxt
        arr.append(states[0])
    return arr, None


def best_insertion(order, arr, c, maxwait):
    """top-2 cheapest feasible mid-tour positions for city c. Returns (best_pos, best_delta, best_cb,
    second_delta) or None. Local delta = (arrival after c->b) - (old arrival at b) = push-back on the suffix.
    Only positions with a->c and c->b both feasible edges are scanned (massive prune); chosen candidate is
    lazily full-retime-validated by the caller. second_delta enables REGRET ordering (insert constrained
    cities, those with few/expensive alternatives, while slack still exists)."""
    best = None; second_delta = float("inf")
    for p in range(len(order) - 1):
        a, b = order[p], order[p + 1]
        if c not in OUTADJ[a] or b not in OUTADJ[c]:
            continue
        ac = earliest(a, c, arr[p], maxwait)
        if ac is None:
            continue
        cb = earliest(c, b, ac, maxwait)
        if cb is None:
            continue
        delta = cb - arr[p + 1]
        if best is None or delta < best[1]:
            second_delta = best[1] if best is not None else second_delta
            best = (p, delta, cb)
        elif delta < second_delta:
            second_delta = delta
    a = order[-1]                                               # append at frontier
    if c in OUTADJ[a]:
        ac = earliest(a, c, arr[-1], maxwait)
        if ac is not None:
            delta = ac - arr[-1]
            if best is None or delta < best[1]:
                second_delta = best[1] if best is not None else second_delta
                best = (len(order) - 1, delta, ac)
            elif delta < second_delta:
                second_delta = delta
    if best is None:
        return None
    return (best[0], best[1], best[2], second_delta)


def insert_all(order, arr, missing, maxwait, validate=True):
    """regret-2 insert as many missing cities as possible into (order, arr). Returns (order, arr, missing_left).
    Pure (no print/checkpoint) so the LNS loop can call it per move. validate=False skips the lazy full-retime
    (trusts the local delta) for speed inside the loop; the accepted best is always re-validated by the caller."""
    missing = list(missing)
    while missing:
        pick = None                                             # (regret, city, pos, cb)
        for c in missing:
            ins = best_insertion(order, arr, c, maxwait)
            if ins is None:
                continue
            p, delta, cb, second = ins
            regret = (second - delta) if second < float("inf") else 1e9 + (-delta)
            if pick is None or regret > pick[0]:
                pick = (regret, c, p, cb)
        if pick is None:
            break                                               # no remaining city has a feasible slot
        _, c, p, cb = pick
        neworder = order[:p + 1] + [c] + order[p + 1:]
        newarr, st = retime(neworder, maxwait, stop_on_strand=True)
        if st is not None:                                      # suffix stranded -> this city can't go here now
            missing.remove(c); continue
        order, arr = neworder, newarr; missing.remove(c)
    return order, arr, missing


def repair(order, maxwait, tag, t0):
    visited = set(order)
    missing = [c for c in cities if c not in visited]
    arr, _ = retime(order, maxwait, stop_on_strand=False)
    order, arr, missing = insert_all(order, arr, missing, maxwait)
    json.dump({"path": order, "makespan": arr[-1], "depth": len(order)},
              open(f"{ROOT}/cache/ch2_giant_completion_{tag}.json", "w"))
    print(f"[E-727][{tag}] single-pass FINAL depth {len(order)}/{NG} makespan {arr[-1]:.1f}d "
          f"(d/leg {arr[-1]/max(len(order)-1,1):.3f}) missing {len(missing)} [{time.time()-t0:.0f}s]", flush=True)
    return order, arr, missing


def lns_loop(seed, maxwait, tag, t0, iters=100000):
    """ALNS destroy-repair: single-pass insertion dead-ends (deterministic, local). Each iter: DESTROY a window
    of cities biased toward the largest-wait legs (the rank-2-pace insertions that block completion), then
    REGRET-repair. Accept on (depth, -makespan) lexicographic; periodically accept sideways to escape. Goal:
    push depth->601 while makespan stays <424 (rank-1). Checkpoints best to cache/."""
    arr, _ = retime(seed, maxwait, stop_on_strand=False)
    order, arr, missing = insert_all(seed, arr, [c for c in cities if c not in set(seed)], maxwait)
    cur = (order, arr, missing)
    best = (list(order), list(arr), list(missing))
    ckpt = f"{ROOT}/cache/ch2_giant_completion_lns_{tag}.json"

    def score(s):                                              # higher is better: more cities, then less makespan
        return (len(s[0]), -s[1][-1])
    print(f"[E-727][{tag}] LNS start depth {len(order)}/{NG} mk {arr[-1]:.1f}d [{time.time()-t0:.0f}s]",
          flush=True)
    rng = 12345
    for it in range(iters):
        order, arr, missing = cur
        rng = (rng * 1103515245 + 12345) & 0x7fffffff          # deterministic LCG (no Math.random dependence)
        # DESTROY: remove ONE contiguous window (single gap -> bridgeable by one insertion; two windows would
        # leave two simultaneous gaps and deadlock the per-insertion lazy validation). Bias half the time to the
        # worst-wait leg (the rank-2-pace cost), half to a random spot (diversify which adjacencies get rebuilt).
        waits = [arr[p + 1] - arr[p] for p in range(len(order) - 1)]
        wlen = 4 + (rng % 9)                                   # 4..12 cities
        if rng % 2 == 0 and waits:
            wp = max(range(len(waits)), key=lambda p: waits[p])
            lo = max(1, wp - wlen // 2)                         # keep order[0] anchor
        else:
            lo = 1 + (rng % max(1, len(order) - wlen - 1))
        rmset = set(order[lo: lo + wlen])
        norder = [c for c in order if c not in rmset]
        # do NOT require the gapped order feasible here (the re-join a->b strands until a bridge is inserted);
        # penalty-carry retime gives a ranking arr, insert_all re-bridges the gap, then we validate the result.
        narr, _ = retime(norder, maxwait, stop_on_strand=False)
        nmiss = list(missing) + list(rmset)
        norder, narr, nmiss = insert_all(norder, narr, nmiss, maxwait)
        fnarr, st = retime(norder, maxwait, stop_on_strand=True)  # validate: gap actually re-bridged?
        if st is not None:
            continue                                           # could not re-bridge the gap -> discard move
        cand = (norder, fnarr, nmiss)
        accept = score(cand) >= score(cur) or (rng % 20 == 0 and len(cand[0]) >= len(cur[0]) - 3)
        if accept:
            cur = cand
        if score(cand) > score(best):
            best = (list(norder), list(narr), list(nmiss))
            json.dump({"path": norder, "makespan": narr[-1], "depth": len(norder)}, open(ckpt, "w"))
            print(f"[E-727][{tag}] LNS it{it}: NEW best depth {len(norder)}/{NG} mk {narr[-1]:.1f}d "
                  f"(d/leg {narr[-1]/max(len(norder)-1,1):.3f}) [{time.time()-t0:.0f}s]", flush=True)
            if len(norder) == NG and narr[-1] < 425:
                print(f"[E-727][{tag}] *** COMPLETE 601 @ {narr[-1]:.0f}d < 425 -> RANK-1! verify officially.",
                      flush=True)
        if it % 200 == 0:
            print(f"[E-727][{tag}] LNS it{it}: cur depth {len(cur[0])} mk {cur[1][-1]:.1f}d | best depth "
                  f"{len(best[0])} mk {best[1][-1]:.1f}d [{time.time()-t0:.0f}s]", flush=True)


def cls_loop(seed, maxwait, tag, t0, iters=2000000):
    """COMPLETE-order penalty local search — the robust-against-strands method (answers 'why can't we allocate
    all cities?'). Every constructive method (beam/GRASP/insertion) DROPS cities it can't place. This instead
    keeps ALL 601 in the order at all times and minimises (n_strands, makespan) by or-opt relocations + SA, so
    it can never 'fail to allocate' — it drives infeasible legs to zero. Seed = any complete order (static LKH
    is TD-infeasible ~163 strands); success = reach 0 strands = a second complete solution, NOT the OR-Tools
    recipe. Then keep descending makespan toward rank-1 (<425d)."""
    order = [int(c) for c in seed]
    mk, st, slegs, hist, cum = retime_full(order, maxwait)
    cur = (order, mk, st, slegs, hist, cum); best = (list(order), mk, st)
    ckpt = f"{ROOT}/cache/ch2_giant_cls_{tag}.json"
    print(f"[E-727][{tag}] CLS start: complete order {len(order)} cities -> {st} strands, makespan {mk:.1f}d "
          f"[{time.time()-t0:.0f}s]", flush=True)
    rng = (sum(ord(ch) * (i + 7) for i, ch in enumerate(tag)) * 2654435761) & 0x7fffffff or 987654321
    n = len(order); acc = 0                                     # rng seeded from tag -> chains on same seed diverge
    # E-729: the rank-1 obstacle is LOW-DEGREE cities (~7-14 cheap preds vs median 152). To place one cheaply its
    # immediate predecessor must be one of its ~10 cheap preds (~1.7% random hit) -> random moves never satisfy it.
    # Precompute giant-restricted cheap pred/succ sets + the low-degree set; targeted "cheap-slot" move places a
    # stranded low-degree city between a cheap pred and a cheap succ.
    GID = set(cities)
    CP = {c: (INADJ[c] & GID) for c in cities}; CS = {c: (OUTADJ[c] & GID) for c in cities}
    LOWDEG = set(c for c in cities if min(len(CP[c]), len(CS[c])) <= 30)
    for it in range(iters):
        order, mk, st, slegs, hist, cum = cur
        rng = (rng * 1103515245 + 12345) & 0x7fffffff
        cand = None
        # MOVE 1 (cheap-slot, E-729): if a stranded leg involves a low-degree city, relocate it between one of its
        # cheap preds and cheap succs -> directly satisfies its rare entry/exit constraint.
        if slegs:
            scl = [c for p in slegs for c in (order[p], order[p + 1]) if c in LOWDEG]
            if scl and (rng % 3 != 0):
                c = scl[rng % len(scl)]
                ci = order.index(c); rest = order[:ci] + order[ci + 1:]
                slots = [p for p in range(len(rest) - 1) if rest[p] in CP[c] and rest[p + 1] in CS[c]]
                if not slots:
                    slots = [p for p in range(len(rest) - 1) if rest[p] in CP[c]]   # at least cheap entry
                if slots:
                    sp = slots[(rng >> 7) % len(slots)]
                    cand = rest[:sp + 1] + [c] + rest[sp + 1:]
        if cand is None:                                       # MOVE 2/3: strand-targeted or plain or-opt relocate
            if slegs and (rng % 4 != 0):
                sp = slegs[rng % len(slegs)]; a = min(max(1, sp + ((rng >> 5) & 1)), n - 2); L = 1
            else:
                L = 1 + (rng % 3); a = 1 + (rng % (n - L - 1))
            seg = order[a:a + L]; rest = order[:a] + order[a + L:]
            b = 1 + ((rng >> 8) % (len(rest) - 1))
            cand = rest[:b] + seg + rest[b:]
        q = 0                                                  # first divergence; leg q-1 may change -> restart q-1
        while q < n and q < len(cand) and cand[q] == order[q]:
            q += 1
        q = max(0, q - 1)
        cmk, cst = retime_inc(cand, q, hist[q], cum[q], maxwait)
        # accept: fewer strands always; equal strands & not-worse makespan; rare uphill (escape local minima)
        if cst < st or (cst == st and cmk <= mk) or ((rng % 40 == 0) and cst <= st + 1):
            _, _, cslegs, chist, ccum = retime_full(cand, maxwait)  # accepted -> rebuild cache for next moves
            cur = (cand, cmk, cst, cslegs, chist, ccum); acc += 1
        if (cst, cmk) < (best[2], best[1]):
            best = (list(cand), cmk, cst)
            json.dump({"path": cand, "makespan": cmk, "depth": n, "strands": cst}, open(ckpt, "w"))
            print(f"[E-727][{tag}] CLS it{it}: NEW best strands {cst} makespan {cmk:.1f}d "
                  f"(d/leg {cmk/(n-1):.3f}) acc {acc} [{time.time()-t0:.0f}s]", flush=True)
            if cst == 0:
                print(f"[E-727][{tag}] *** 0 STRANDS — complete feasible tour {cmk:.0f}d via local search "
                      f"(NOT OR-Tools) = robust reproduction! {'RANK-1!' if cmk < 425 else ''}", flush=True)
        # NB: ILS kicks were tried and REMOVED — extreme timing fragility means ANY perturbation that shifts early
        # timing cascades (3-city relocation: 2 strands -> 107). Escape must come from non-cascading (tail) moves,
        # which the strand-targeted/cheap-slot moves already attempt. See E-729.
        if it % 100 == 0:
            print(f"[E-727][{tag}] CLS it{it}: cur strands {cur[2]} mk {cur[1]:.1f}d | best strands {best[2]} "
                  f"mk {best[1]:.1f}d | acc {acc} [{time.time()-t0:.0f}s]", flush=True)


def main(seed_json="grasp_best_k", maxwait=40, tag="k", mode="single"):
    ft.transfer_dv(OPAR[0], OPAR[1], 10 * DAY, 1 * DAY, MAXREV)  # JIT warm
    if seed_json.startswith("grasp_best_"):
        seed_json = f"{ROOT}/cache/ch2_giant_faithful_grasp_best_{seed_json.split('_')[-1]}.json"
    obj = json.load(open(seed_json)); seed = [int(c) for c in (obj["path"] if isinstance(obj, dict) else obj)]
    t0 = time.time()
    arr, strand = retime(seed, maxwait, stop_on_strand=True)
    print(f"[E-727][{tag}] SEED depth {len(seed)}/{NG} retimes to {'STRAND@'+str(strand) if strand is not None else 'full'} "
          f"makespan {arr[-1]:.1f}d (d/leg {arr[-1]/max(len(seed)-1,1):.3f}) maxwait={maxwait} mode={mode} "
          f"[positive-control {time.time()-t0:.0f}s]", flush=True)
    if mode == "lns":
        lns_loop(seed, maxwait, tag, t0)
    elif mode == "cls":
        cls_loop(seed, maxwait, tag, t0)
    else:
        repair(seed, maxwait, tag, t0)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else "grasp_best_k", float(a[2]) if len(a) > 2 else 40.0,
         a[3] if len(a) > 3 else "k", a[4] if len(a) > 4 else "single")
