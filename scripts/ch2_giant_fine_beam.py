"""E-710 M2 — fine-tof BEAM for the 601-giant: the time-aware decomposition core.

Foundation (M0a-c, validated): table is 100% faithful; cheap-tof bands ~0.002d (coarse scans miss 89%);
cheap windows continuous & wide (~12d). So a beam that (a) prunes candidates with the table, (b) verifies
each with a FINE table-seeded tof search (exact, ~bounded Lamberts), (c) carries exact running time per
state, builds order+timing together with no overfit. Width W>1 gives the GLOBAL LOOKAHEAD that pure greedy
(walls at 367/601 via frontier exhaustion) lacks: keep W states ranked by makespan, so promising-but-not-
greediest branches survive to thread the tail.

Instrumented (depth/W/best-t each step, positive control in <2min); checkpoints best path to a reboot-
surviving cache every 25 depths; resumable. Reports deepest/complete order + faithful makespan.
Usage: python ch2_giant_fine_beam.py [W=60] [K=18] [start=-1(auto)]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
CKPT = f"{ROOT}/cache/ch2_giant_fine_beam_best.json"
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
OUT = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    OUT[int(i)].append((int(j), r))
# pre-sort each city's neighbors by the edge's global-min table tof (cheapest-looking first)
GMIN = np.where(FIN.any(1), np.nanmin(np.where(FIN, VALS, np.inf), 1), np.inf)
for i in OUT:
    OUT[i].sort(key=lambda jr: GMIN[jr[1]])


def fine_cheap_arrival(i, j, row, t, dv_cap):
    """Earliest <=dv_cap arrival for edge (i,j) departing >= t. Table proposes the open epoch &
    tof; fine local verify. Returns (departure, tof, arrival) or None. ~bounded Lamberts."""
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):       # nearest open grid epochs (windows wide)
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= dv_cap:
                return dep, float(tof), dep + float(tof)
    return None


def candidates(i, t, visited, K, exc_left):
    """Cheap (<=dv_thr) candidates first; if few and exceptions remain, add EXCEPTION (<=dv_exc) candidates
    for hard transitions. Returns (city, arrival, tof, is_exc)."""
    out = []
    for (j, row) in OUT[i]:
        if j in visited:
            continue
        res = fine_cheap_arrival(i, j, row, t, kt.dv_thr)
        if res is not None:
            out.append((j, res[2], res[1], 0))                     # (city, arrival, tof, is_exc)
            if len(out) >= K * 3:
                break
    out.sort(key=lambda c: c[1])
    out = out[:K]
    if len(out) < 4 and exc_left > 0:                             # ONLY a near-stuck frontier spends an exception
        have = {c[0] for c in out}; exc = []
        for (j, row) in OUT[i][:40]:                              # bounded scan (neighbors sorted cheapest-first)
            if j in visited or j in have:
                continue
            res = fine_cheap_arrival(i, j, row, t, kt.dv_exc)
            if res is not None:
                exc.append((j, res[2], res[1], 1))
                if len(exc) >= 4:
                    break
        exc.sort(key=lambda c: c[1])
        out = out + exc
    return out[:K]


def main(W=60, K=18, start=-1):
    starts = [cities[start]] if start >= 0 else cities[:8]
    print(f"[E-710 M2] fine-tof beam W={W} K={K}; giant n={NG}; {len(starts)} seed start(s)", flush=True)
    # beam states: dict(last, t, exc, visited frozenset-ish via tuple-sorted? use set + path)
    beam = [{"t": 0.0, "last": s, "vis": {s}, "path": [s], "exc": 0} for s in starts]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t": 0.0}
    t0 = time.time(); pc_done = False
    for depth in range(1, NG):
        succ = []
        for st in beam:
            cs = candidates(st["last"], st["t"], st["vis"], K, kt.n_exc - st["exc"])
            for (j, arr, tof, is_exc) in cs:
                succ.append({"t": arr, "last": j, "vis": st["vis"] | {j},
                             "path": st["path"] + [j], "exc": st["exc"] + is_exc})
        if not pc_done:
            print(f"[E-710 M2] positive control: depth1 expanded to {len(succ)} successors [{time.time()-t0:.0f}s]", flush=True)
            pc_done = True
        if not succ:
            print(f"[E-710 M2] beam stranded at depth {depth} (no successor from any of {len(beam)} states)", flush=True)
            break
        succ.sort(key=lambda s: s["t"])                            # keep W earliest-time states
        # light diversity: dedup by last city, keep best-time per last, then fill by time
        seen = set(); pruned = []
        for s in succ:
            if s["last"] in seen:
                continue
            seen.add(s["last"]); pruned.append(s)
            if len(pruned) >= W:
                break
        beam = pruned if len(pruned) >= W // 2 else succ[:W]
        deepest = max(beam, key=lambda s: len(s["path"]))
        if len(deepest["path"]) > best["depth"]:
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]), "t": deepest["t"]}
        if depth % 20 == 0 or depth < 5:
            bt = min(beam, key=lambda s: s["t"])
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} "
                  f"min_t={bt['t']:.1f}d (d/leg {bt['t']/max(len(bt['path'])-1,1):.3f}) [{time.time()-t0:.0f}s]", flush=True)
        if depth % 25 == 0:
            json.dump(best, open(CKPT, "w"))
    print(f"\n[E-710 M2] DONE: deepest order {best['depth']}/{NG} cities, makespan {best['t']:.1f}d "
          f"(d/leg {best['t']/max(best['depth']-1,1):.3f}); rank-1=424.62, prior greedy wall=367 [{time.time()-t0:.0f}s]", flush=True)
    json.dump(best, open(CKPT, "w"))
    if best["depth"] >= NG - 2 and best["t"] < 500:
        print(f"[E-710 M2] *** beam THREADS the full giant at {best['t']:.0f}d -> rank-1 territory. "
              f"Next: stitch the 3x150 satellites + faithful udp verify + guard-bank.", flush=True)
    elif best["depth"] > 420:
        print(f"[E-710 M2] beam threads {best['depth']}/601 (past the 367 wall) -> lookahead helps; widen W/K.", flush=True)
    else:
        print(f"[E-710 M2] beam walls near greedy ({best['depth']}); frontier exhaustion is W-resistant -> "
              f"need true decomposition (cluster by window-epoch + intra-cluster fine-tof TSP), not just beam.", flush=True)


if __name__ == "__main__":
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 18
    s = int(sys.argv[3]) if len(sys.argv) > 3 else -1
    main(W, K, s)
