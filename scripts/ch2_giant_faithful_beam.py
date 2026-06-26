"""E-726b — Ch2-large rank-1: coverage beam on the FAITHFUL epoch-dense numba evaluator (E-725).

Audit E-726: the time-aware beam already threads 558@283d (rank-1 PACE); the cap is COMPLETENESS, and it
stalled because it searched the epoch-SPARSE table (~6 windows/edge). The faithful numba evaluator sees the
same edges cheap at ~100x more epochs -> far more window options at the stranding frontier. This re-runs a
coverage-elite forward beam with per-edge windows from the numba scanner (cached), aiming to thread past 575
toward 601 at ~0.5 d/leg. Candidate neighbours from the table adjacency (validated complete at pair level);
arrival times from numba (epoch-dense). Opportunistic rare-city capture + coverage-elite diversity.
Usage: python ch2_giant_faithful_beam.py [W_core=80] [W_cov=60] [K=18] [thresh=40] [Radd=8] [start=-1]"""
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
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(int(i) for i in set(KEYS[:, 0]) | set(KEYS[:, 1]))); NG = len(cities)
OUTADJ = defaultdict(list); INc = defaultdict(set)
GMIN = {}
for r, (i, j) in enumerate(KEYS):
    i, j = int(i), int(j)
    if FIN[r].any():
        OUTADJ[i].append(j); INc[j].add(i); GMIN[(i, j)] = float(np.nanmin(VALS[r]))
INDEG = {c: len(INc[c]) for c in cities}
for i in OUTADJ:
    OUTADJ[i].sort(key=lambda j: GMIN.get((i, j), 9.0))          # prefer short-min-tof neighbours
DEPS = np.arange(0.0, 460.0, 0.2)                                # epoch grid (days)
DEPS_SEC = DEPS * DAY
# load the precomputed FAITHFUL epoch-dense short-tof window table (E-726d) -> instant lookups
_PC = f"{ROOT}/cache/ch2_giant_faithful_windows.npz"
_CACHE = {}
if os.path.exists(_PC):
    _CACHE = np.load(_PC, allow_pickle=True)["windows"].item()
    print(f"[E-726b] loaded {len(_CACHE)} precomputed faithful edges", flush=True)


_EMPTY = (np.array([]), np.array([]))


def edge_windows(i, j):
    return _CACHE.get((i, j), _EMPTY)                            # pure lookup (precomputed short-tof edges only)


def earliest(i, j, t, maxwait):
    deps, tofs = edge_windows(i, j)
    if len(deps) == 0:
        return None
    q = np.searchsorted(deps, t)
    if q < len(deps) and deps[q] <= t + maxwait:
        return float(deps[q] + tofs[q])
    return None


def dedup(states, key, n):
    states = sorted(states, key=key); seen = set(); keep = []
    for s in states:
        if s["last"] in seen:
            continue
        seen.add(s["last"]); keep.append(s)
        if len(keep) >= n:
            break
    return keep


def main(W_core=80, W_cov=60, K=18, thresh=40, Radd=8, start=-1, maxwait=20):
    ft.transfer_dv(OPAR[0], OPAR[1], 10 * DAY, 1 * DAY, MAXREV)
    RARE = set(c for c in cities if INDEG[c] < thresh)
    starts = [cities[start]] if start >= 0 else cities[:8]
    print(f"[E-726b] faithful coverage beam W_core={W_core} W_cov={W_cov} K={K} |RARE|={len(RARE)} "
          f"Radd={Radd}; n={NG}; {len(starts)} seeds", flush=True)
    beam = [{"t": 0.0, "last": s, "vis": {s}, "path": [s], "rare": int(s in RARE)} for s in starts]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t": 0.0}
    t0 = time.time()
    for depth in range(1, NG):
        succ = []
        for st in beam:
            cand = []
            for j in OUTADJ[st["last"]]:
                if j in st["vis"]:
                    continue
                a = earliest(st["last"], j, st["t"], maxwait)
                if a is not None:
                    cand.append((j, a))
                    if len(cand) >= K * 3:
                        break
            cand.sort(key=lambda c: c[1]); core = cand[:K]
            have = {j for j, _ in core}; radd = 0
            for j in OUTADJ[st["last"]]:                          # opportunistic rare capture
                if radd >= Radd:
                    break
                if j in st["vis"] or j in have or j not in RARE:
                    continue
                a = earliest(st["last"], j, st["t"], maxwait)
                if a is not None:
                    core.append((j, a)); have.add(j); radd += 1
            for (j, a) in core:
                succ.append({"t": a, "last": j, "vis": st["vis"] | {j}, "path": st["path"] + [j],
                             "rare": st["rare"] + (j in RARE)})
        if not succ:
            print(f"[E-726b] stranded at depth {depth} [{time.time()-t0:.0f}s]", flush=True)
            break
        core = dedup(succ, lambda s: s["t"], W_core)
        cov = dedup(succ, lambda s: (-s["rare"], s["t"]), W_cov)
        merged = {id(s): s for s in core}
        for s in cov:
            merged[id(s)] = s
        beam = list(merged.values())
        deepest = max(beam, key=lambda s: len(s["path"]))
        if (len(deepest["path"]), -deepest["t"]) > (best["depth"], -best["t"]):
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]), "t": deepest["t"]}
        if depth % 20 == 0 or depth < 3:
            bt = min(beam, key=lambda s: s["t"])
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} min_t={bt['t']:.1f}d "
                  f"(d/leg {bt['t']/max(len(bt['path'])-1,1):.3f}) edges={len(_CACHE)} [{time.time()-t0:.0f}s]",
                  flush=True)
        if depth % 25 == 0:
            json.dump(best, open(f"{ROOT}/cache/ch2_giant_faithful_beam_best.json", "w"))
    rin = sum(1 for c in best["path"] if c in RARE)
    print(f"\n[E-726b] DONE deepest {best['depth']}/{NG} makespan {best['t']:.1f}d "
          f"(d/leg {best['t']/max(best['depth']-1,1):.3f}) rare {rin}/{len(RARE)} "
          f"[vs E-710 558@283d / cap 575] [{time.time()-t0:.0f}s]", flush=True)
    json.dump(best, open(f"{ROOT}/cache/ch2_giant_faithful_beam_best.json", "w"))
    if best["depth"] > 575:
        print(f"[E-726b] *** {best['depth']}/601 > 575 -> faithful epoch-dense breaks the corner-paint cap!",
              flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 80, int(a[2]) if len(a) > 2 else 60, int(a[3]) if len(a) > 3 else 18,
         int(a[4]) if len(a) > 4 else 40, int(a[5]) if len(a) > 5 else 8, int(a[6]) if len(a) > 6 else -1)
