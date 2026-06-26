"""E-722c — Ch2-large rank-1: ROLLOUT / lookahead-augmented forward beam (anti-corner-painting).

Forward beam caps ~575 because it ranks states by EARLIEST ARRIVAL and commits to a frontier from which the
remaining cluster isn't phase-reachable (E-722 corner-painting). Fail-first and width didn't break it. The
standard fix: judge each candidate not by its immediate arrival but by its COMPLETABILITY — a short greedy
rollout estimating how many more cities it can still thread. A state that arrives slightly later but keeps 580
cities reachable beats one that arrives early into a dead-end.

Method: standard candidate expansion; first-pass arrival-prune to top 2W (cheap); then a greedy W=1 rollout
(earliest-cheap, R steps) from each survivor; keep top W by `arrival - LAM*rollout_reach`. Rollout is the
lookahead that pure beam lacks. Reuses the corrected graph + fine oracle.
Usage: python ch2_giant_rollout_beam.py [W=140] [K=16] [R=14] [LAM=3.0] [start=-1]
Env CH2_TABLE: cache/ch2_giant_dense1d_aug.npz"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d_aug.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
OUT = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    OUT[int(i)].append((int(j), r))
GMIN = np.where(FIN.any(1), np.nanmin(np.where(FIN, VALS, np.inf), 1), np.inf)
for i in OUT:
    OUT[i].sort(key=lambda jr: GMIN[jr[1]])


def fine_arr(i, j, row, t, cap):
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= cap:
                return dep + float(tof)
    return None


def best_cheap_next(i, t, vis):
    """single cheapest-arrival unvisited successor (for rollout)."""
    for (j, row) in OUT[i]:
        if j in vis:
            continue
        a = fine_arr(i, j, row, t, kt.dv_thr)
        if a is not None:
            return j, a
    return None


def rollout_reach(i, t, vis, R):
    """greedy W=1 lookahead: how many more cities reachable in R steps from (i,t,vis)."""
    cur = i; ct = t; seen = set(vis); reached = 0
    for _ in range(R):
        nx = best_cheap_next(cur, ct, seen)
        if nx is None:
            break
        cur, ct = nx; seen.add(cur); reached += 1
    return reached


def candidates(i, t, vis, K, exc_left):
    out = []
    for (j, row) in OUT[i]:
        if j in vis:
            continue
        a = fine_arr(i, j, row, t, kt.dv_thr)
        if a is not None:
            out.append((j, a, 0))
            if len(out) >= K * 3:
                break
    out.sort(key=lambda c: c[1]); out = out[:K]
    if len(out) < 4 and exc_left > 0:
        have = {c[0] for c in out}
        for (j, row) in OUT[i][:40]:
            if j in vis or j in have:
                continue
            a = fine_arr(i, j, row, t, kt.dv_exc)
            if a is not None:
                out.append((j, a, 1))
                if sum(c[2] for c in out) >= 4:
                    break
    return out


def dedup_keep(states, key, n):
    states = sorted(states, key=key); seen = set(); keep = []
    for s in states:
        if s["last"] in seen:
            continue
        seen.add(s["last"]); keep.append(s)
        if len(keep) >= n:
            break
    return keep


def main(W=140, K=16, R=14, LAM=3.0, start=-1):
    CKPT = f"{ROOT}/cache/ch2_giant_rollout_beam_w{W}_r{R}_l{LAM}.json"
    starts = [cities[start]] if start >= 0 else cities[:8]
    print(f"[E-722c] rollout-beam W={W} K={K} R={R} LAM={LAM}; n={NG}; {len(starts)} seed(s)", flush=True)
    beam = [{"t": 0.0, "last": s, "vis": {s}, "path": [s], "exc": 0} for s in starts]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t": 0.0}
    t0 = time.time(); pc = False
    for depth in range(1, NG):
        succ = []
        for st in beam:
            for (j, arr, is_exc) in candidates(st["last"], st["t"], st["vis"], K, kt.n_exc - st["exc"]):
                succ.append({"t": arr, "last": j, "vis": st["vis"] | {j}, "path": st["path"] + [j],
                             "exc": st["exc"] + is_exc})
        if not pc:
            print(f"[E-722c] positive control: depth1 -> {len(succ)} successors [{time.time()-t0:.0f}s]", flush=True)
            pc = True
        if not succ:
            print(f"[E-722c] beam stranded at depth {depth}", flush=True)
            break
        survivors = dedup_keep(succ, lambda s: s["t"], 2 * W)            # cheap arrival pre-prune
        for s in survivors:                                              # ROLLOUT only the survivors
            s["score"] = s["t"] - LAM * rollout_reach(s["last"], s["t"], s["vis"], R)
        beam = dedup_keep(survivors, lambda s: s["score"], W)            # keep most-completable
        deepest = max(beam, key=lambda s: len(s["path"]))
        if (len(deepest["path"]), -deepest["t"]) > (best["depth"], -best["t"]):
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]), "t": deepest["t"]}
        if depth % 20 == 0 or depth < 5:
            bt = min(beam, key=lambda s: s["t"])
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} min_t={bt['t']:.1f}d "
                  f"(d/leg {bt['t']/max(len(bt['path'])-1,1):.3f}) [{time.time()-t0:.0f}s]", flush=True)
        if depth % 25 == 0:
            json.dump(best, open(CKPT, "w"))
    print(f"\n[E-722c] DONE: deepest {best['depth']}/{NG}, makespan {best['t']:.1f}d "
          f"(d/leg {best['t']/max(best['depth']-1,1):.3f}); forward-beam cap=575 [{time.time()-t0:.0f}s]", flush=True)
    json.dump(best, open(CKPT, "w"))
    if best["depth"] > 575:
        print(f"[E-722c] *** {best['depth']}/601 > 575 -> rollout breaks corner-paint; push toward 601@<405d.", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 140, int(a[2]) if len(a) > 2 else 16,
         int(a[3]) if len(a) > 3 else 14, float(a[4]) if len(a) > 4 else 3.0,
         int(a[5]) if len(a) > 5 else -1)
