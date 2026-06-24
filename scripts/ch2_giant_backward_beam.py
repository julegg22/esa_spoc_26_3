"""E-719c — Ch2-large rank-1: BACKWARD beam (meet-in-the-middle, step A1).

The forward coverage beam caps at ~566/601: it strands ~35 cities REACHABLE-FROM-PASSED-cities (forward
myopia, makespan 298d << 424 so budget is fine). A BACKWARD beam builds the tour END->START, so it strands
cities reachable-from-FUTURE — the mirror failure. If the backward-stranded set is DISJOINT from the
forward-stranded 35, a meet-in-the-middle join covers all 601 (each half supplies what the other misses);
if it strands the SAME cities, they are bidirectionally hard and rank-1 is likely beam-infeasible.

Backward transfer oracle (mirror of fine_cheap_arrival): city c must be ARRIVED-AT at exactly t_arr; find a
predecessor p's departure t_p (<= t_arr) with compute_transfer(p,c,t_p, t_arr-t_p) <= dv_cap. The suffix is
built at ABSOLUTE times anchored to end-time T (transfers are time-dependent, so relative-build+shift would
break feasibility). Prune by LATEST t_first (mirror of forward's earliest-arrival) + coverage-elite for rare.
Reports the backward order + its stranded set; compares to the forward-stranded 35.
Usage: python ch2_giant_backward_beam.py [T=420] [W_core=70] [W_cov=40] [K=18] [thresh=40] [Radd=6]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
CKPT = f"{ROOT}/cache/ch2_giant_backward_beam_best.json"
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
IN = defaultdict(list)                                          # c -> [(p,row)] cheap in-edges (predecessors)
ROW = {}                                                        # (p,c) -> row, O(1) lookup
for r, (i, j) in enumerate(KEYS):
    IN[int(j)].append((int(i), r)); ROW[(int(i), int(j))] = r
GMIN = np.where(FIN.any(1), np.nanmin(np.where(FIN, VALS, np.inf), 1), np.inf)
for c in IN:
    IN[c].sort(key=lambda pr: GMIN[pr[1]])
INDEG = {c: len({p for (p, r) in IN[c] if FIN[r].any()}) for c in cities}
ARRV = EPOCHS[None, :] + np.where(FIN, VALS, np.inf)            # arrival if departing at each epoch (min-tof)


def back_cheap_dep(p, c, t_arr, dv_cap):
    """latest departure t_p with a <=dv_cap transfer p->c ARRIVING at ~t_arr. (t_p, tof) or None.
    Vectorized: only fine-scan epochs whose min-tof arrival lands within ~1.5d of t_arr."""
    row = ROW.get((p, c))
    if row is None:
        return None
    cand = np.where(np.abs(ARRV[row] - t_arr) < 1.5)[0]        # epochs that (with min-tof) arrive near t_arr
    for e in cand[::-1]:                                        # latest departure first
        h = float(VALS[row, e])
        for dep in np.arange(EPOCHS[e] - 0.03, EPOCHS[e] + 0.05, 0.0005):
            tof = t_arr - dep
            if tof < kt.min_tof or abs(tof - h) > 0.08:
                continue
            if kt.compute_transfer(p, c, float(dep), float(tof)) <= dv_cap:
                return float(dep), float(tof)
    return None


def back_candidates(c, t_in, visited, K, exc_left, RARE, Radd):
    """predecessors p of c that can ARRIVE at c at t_in cheaply; cheapest (latest-departure) first +
    opportunistic rare + exceptions when near-stuck. Returns (p, t_p, tof, is_exc)."""
    out = []
    for (p, row) in IN[c]:
        if p in visited:
            continue
        r = back_cheap_dep(p, c, t_in, kt.dv_thr)
        if r is not None:
            out.append((p, r[0], r[1], 0))
            if len(out) >= K * 3:
                break
    out.sort(key=lambda x: -x[1])                              # latest departure first (mirror earliest-arr)
    out = out[:K]
    have = {x[0] for x in out}
    radded = 0
    for (p, row) in IN[c]:
        if radded >= Radd:
            break
        if p in visited or p in have or p not in RARE:
            continue
        r = back_cheap_dep(p, c, t_in, kt.dv_thr)
        if r is not None:
            out.append((p, r[0], r[1], 0)); have.add(p); radded += 1
    if len([x for x in out if x[3] == 0]) < 4 and exc_left > 0:
        for (p, row) in IN[c][:40]:
            if p in visited or p in have:
                continue
            r = back_cheap_dep(p, c, t_in, kt.dv_exc)
            if r is not None:
                out.append((p, r[0], r[1], 1)); have.add(p)
                if sum(x[3] for x in out) >= 4:
                    break
    return out


def dedup_keep(states, key, n):
    states = sorted(states, key=key)
    seen = set(); keep = []
    for s in states:
        if s["first"] in seen:
            continue
        seen.add(s["first"]); keep.append(s)
        if len(keep) >= n:
            break
    return keep


def main(T=420.0, W_core=70, W_cov=40, K=18, thresh=40, Radd=6):
    RARE = set(c for c in cities if INDEG[c] < thresh)
    # seed: each candidate LAST city arriving at T (use the 8 lowest-id as forward did, symmetric)
    seeds = cities[:8]
    print(f"[E-719c] BACKWARD beam T={T} W_core={W_core} W_cov={W_cov} K={K} thresh={thresh} "
          f"(|RARE|={len(RARE)}) Radd={Radd}; n={NG}", flush=True)
    beam = [{"t_first": T, "first": s, "vis": {s}, "path": [s], "exc": 0, "rare": int(s in RARE)} for s in seeds]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t_first": T, "rare": beam[0]["rare"]}
    t0 = time.time(); pc = False
    for depth in range(1, NG):
        succ = []
        for st in beam:
            for (p, t_p, tof, is_exc) in back_candidates(st["first"], st["t_first"], st["vis"], K,
                                                         kt.n_exc - st["exc"], RARE, Radd):
                if t_p < 0:
                    continue
                succ.append({"t_first": t_p, "first": p, "vis": st["vis"] | {p},
                             "path": [p] + st["path"], "exc": st["exc"] + is_exc, "rare": st["rare"] + (p in RARE)})
        if not pc:
            print(f"[E-719c] positive control: depth1 -> {len(succ)} predecessors [{time.time()-t0:.0f}s]", flush=True)
            pc = True
        if not succ:
            print(f"[E-719c] backward beam stranded at depth {depth}", flush=True)
            break
        core = dedup_keep(succ, lambda s: -s["t_first"], W_core)                 # latest t_first (most room)
        cov = dedup_keep(succ, lambda s: (-s["rare"], -s["t_first"]), W_cov)
        merged = {id(s): s for s in core}
        for s in cov:
            merged[id(s)] = s
        beam = list(merged.values())
        deepest = max(beam, key=lambda s: len(s["path"]))
        if len(deepest["path"]) > best["depth"]:
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]),
                    "t_first": deepest["t_first"], "rare": deepest["rare"]}
        if depth % 20 == 0 or depth < 5:
            bt = max(beam, key=lambda s: s["t_first"])
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} "
                  f"t_first={bt['t_first']:.1f}d span={T-bt['t_first']:.1f}d "
                  f"(d/leg {(T-bt['t_first'])/max(len(bt['path'])-1,1):.3f}) [{time.time()-t0:.0f}s]", flush=True)
        if depth % 25 == 0:
            json.dump(best, open(CKPT, "w"))
    json.dump(best, open(CKPT, "w"))
    stranded = sorted(set(cities) - set(best["path"]))
    span = T - best["t_first"]
    print(f"\n[E-719c] DONE: backward order {best['depth']}/{NG}, span {span:.1f}d "
          f"(start t={best['t_first']:.1f}, end T={T}); stranded {len(stranded)} [{time.time()-t0:.0f}s]", flush=True)
    # compare to forward-stranded 35
    try:
        fwd = set(json.load(open(f"{ROOT}/cache/ch2_giant_stranded35.json")))
        bwd = set(stranded)
        print(f"[E-719c] forward-stranded={len(fwd)} backward-stranded={len(bwd)} "
              f"OVERLAP={len(fwd & bwd)} | forward-only={len(fwd - bwd)} backward-only={len(bwd - fwd)}", flush=True)
        if len(fwd & bwd) <= 5:
            print(f"[E-719c] *** stranded sets nearly DISJOINT -> meet-in-the-middle can cover all 601. Build join.", flush=True)
        else:
            print(f"[E-719c] {len(fwd & bwd)} cities stranded BOTH ways -> bidirectionally hard; rank-1 likely "
                  f"beam-infeasible for these.", flush=True)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    a = sys.argv
    main(float(a[1]) if len(a) > 1 else 420.0, int(a[2]) if len(a) > 2 else 70,
         int(a[3]) if len(a) > 3 else 40, int(a[4]) if len(a) > 4 else 18,
         int(a[5]) if len(a) > 5 else 40, int(a[6]) if len(a) > 6 else 6)
