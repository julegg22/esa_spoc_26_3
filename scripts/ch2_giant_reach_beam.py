"""E-722 — Ch2-large rank-1: reachability-aware (fail-first) beam.

The coverage beam (E-719b) grabs rare cities REACTIVELY and still caps ~575. Diagnosis (E-721g): every city
is cheaply enterable across the WHOLE horizon (narrowness is in TOF, not epoch), so the ~24 stranded cities
are NOT unreachable — the beam paints itself into a corner by CONSUMING a hard city's few cheap predecessors
without ever visiting it. The distinct lever here is PROACTIVE, not reactive:

  (1) CRITICALITY RISK in the state ranking — penalize states by sum over unvisited HARD cities h of
      w(h)/max(1, #unvisited cheap predecessors of h still ahead). Visiting/burning a predecessor of an
      unvisited hard city RAISES risk, so the beam avoids stranding it (fail-first / most-constrained-first).
  (2) FORCED CAPTURE — when at a predecessor of a hard city that is reachable NOW and has <=Crit unvisited
      predecessors left, force that transition into the candidate set at top priority (grab it before its
      last predecessor is consumed), even at a makespan cost.

Ranking = t + LAM*risk (keep the rank-1 pace via t, but bend the route to keep hard cities reachable).
Usage: python ch2_giant_reach_beam.py [W=120] [K=18] [thresh=22] [LAM=0.5] [Crit=3] [start=-1]
Env CH2_TABLE: cache/ch2_giant_dense1d_aug.npz (the corrected graph)."""
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
PRED = defaultdict(set)                                          # cheap predecessors of each city
for r, (i, j) in enumerate(KEYS):
    if FIN[r].any():
        PRED[int(j)].add(int(i))
INDEG = {c: len(PRED[c]) for c in cities}


def fine_cheap_arrival(i, j, row, t, dv_cap):
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= dv_cap:
                return dep + float(tof)
    return None


def risk(vis, HARD):
    """fail-first criticality: sum over UNVISITED hard cities of 1/max(1, #unvisited preds). A hard city whose
    predecessors are nearly all consumed dominates the sum -> the beam is pushed to grab it first."""
    s = 0.0
    for h in HARD:
        if h in vis:
            continue
        rem = len(PRED[h] - vis)
        s += 1.0 / max(1, rem)
    return s


def candidates(i, t, vis, K, exc_left, HARD, Crit):
    out = []
    for (j, row) in OUT[i]:
        if j in vis:
            continue
        arr = fine_cheap_arrival(i, j, row, t, kt.dv_thr)
        if arr is not None:
            out.append((j, arr, 0))
            if len(out) >= K * 3:
                break
    out.sort(key=lambda c: c[1])
    out = out[:K]
    have = {c[0] for c in out}
    # FORCED CAPTURE: hard cities reachable NOW that are about to lose their last predecessors
    for h in HARD:
        if h in vis or h in have:
            continue
        if len(PRED[h] - vis) > Crit or i not in PRED[h]:        # only if I'm a pred AND h is near-stranded
            continue
        row = next((r for (jj, r) in OUT[i] if jj == h), None)
        if row is None:
            continue
        arr = fine_cheap_arrival(i, h, row, t, kt.dv_thr)
        if arr is not None:
            out.append((h, arr, 0)); have.add(h)
    if len(out) < 4 and exc_left > 0:                            # near-stuck -> exceptions
        for (j, row) in OUT[i][:40]:
            if j in vis or j in have:
                continue
            arr = fine_cheap_arrival(i, j, row, t, kt.dv_exc)
            if arr is not None:
                out.append((j, arr, 1)); have.add(j)
                if sum(c[2] for c in out) >= 4:
                    break
    return out


def dedup_keep(states, key, n):
    states = sorted(states, key=key)
    seen = set(); keep = []
    for s in states:
        if s["last"] in seen:
            continue
        seen.add(s["last"]); keep.append(s)
        if len(keep) >= n:
            break
    return keep


def main(W=120, K=18, thresh=22, LAM=0.5, Crit=3, start=-1):
    HARD = set(c for c in cities if INDEG[c] < thresh)
    CKPT = f"{ROOT}/cache/ch2_giant_reach_beam_w{W}_l{LAM}_c{Crit}.json"
    starts = [cities[start]] if start >= 0 else cities[:8]
    print(f"[E-722] reach-beam W={W} K={K} thresh={thresh} (|HARD|={len(HARD)}) LAM={LAM} Crit={Crit}; "
          f"n={NG}; {len(starts)} seed(s)", flush=True)
    beam = [{"t": 0.0, "last": s, "vis": {s}, "path": [s], "exc": 0} for s in starts]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t": 0.0}
    t0 = time.time(); pc = False
    for depth in range(1, NG):
        succ = []
        for st in beam:
            for (j, arr, is_exc) in candidates(st["last"], st["t"], st["vis"], K, kt.n_exc - st["exc"], HARD, Crit):
                v2 = st["vis"] | {j}
                succ.append({"t": arr, "last": j, "vis": v2, "path": st["path"] + [j],
                             "exc": st["exc"] + is_exc, "score": arr + LAM * risk(v2, HARD)})
        if not pc:
            print(f"[E-722] positive control: depth1 -> {len(succ)} successors [{time.time()-t0:.0f}s]", flush=True)
            pc = True
        if not succ:
            print(f"[E-722] beam stranded at depth {depth}", flush=True)
            break
        beam = dedup_keep(succ, lambda s: s["score"], W)          # rank by t + LAM*risk (fail-first)
        deepest = max(beam, key=lambda s: len(s["path"]))
        if (len(deepest["path"]), -deepest["t"]) > (best["depth"], -best["t"]):
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]), "t": deepest["t"]}
        if depth % 20 == 0 or depth < 5:
            bt = min(beam, key=lambda s: s["t"])
            hin = max(sum(1 for c in s["path"] if c in HARD) for s in beam)
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} min_t={bt['t']:.1f}d "
                  f"(d/leg {bt['t']/max(len(bt['path'])-1,1):.3f}) | max_hard_in_beam={hin}/{len(HARD)} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
        if depth % 25 == 0:
            json.dump(best, open(CKPT, "w"))
    hin = sum(1 for c in best["path"] if c in HARD)
    print(f"\n[E-722] DONE: deepest {best['depth']}/{NG}, makespan {best['t']:.1f}d "
          f"(d/leg {best['t']/max(best['depth']-1,1):.3f}); hard threaded {hin}/{len(HARD)}; "
          f"rank-1=424.62; coverage-beam baseline=575 [{time.time()-t0:.0f}s]", flush=True)
    json.dump(best, open(CKPT, "w"))
    if best["depth"] > 575:
        print(f"[E-722] *** {best['depth']}/601 > 575 (coverage-beam cap) -> fail-first threads more; push.", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 120, int(a[2]) if len(a) > 2 else 18,
         int(a[3]) if len(a) > 3 else 22, float(a[4]) if len(a) > 4 else 0.5,
         int(a[5]) if len(a) > 5 else 3, int(a[6]) if len(a) > 6 else -1)
