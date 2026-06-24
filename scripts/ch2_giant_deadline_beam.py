"""E-719 — Ch2-large rank-1: deadline-aware periphery-interleaving fine-tof beam.

E-710's beam threads 558/601 @ 283d (core at rank-1 pace) but STRANDS ~43 low-degree periphery cities: it
ranks states by EARLIEST ARRIVAL, so it phases the core and defers the periphery until their cheap windows
(which open at EARLY epochs, E-664) have CLOSED. The rank-1 budget is generous — 141.6d for 43 cities =
3.29 d/leg allowed vs the competitor's ~2.7 — so this is a FEASIBILITY problem (can we thread them at all),
not efficiency.

Fix (the one untried lever): keep the proven core machinery, but
  (1) per periphery city, precompute its WINDOW-CLOSING DEADLINE = latest departure epoch with an open
      incoming cheap edge (after which the city is unreachable);
  (2) inject URGENCY candidates: from the current city, a periphery city whose deadline is near is offered
      even if it isn't the earliest-arrival option, so the beam CAN divert to it in time;
  (3) rank states by  t + LAMBDA * (#unvisited periphery already past deadline)  so states that strand
      periphery are deprioritized -> threading states survive pruning.
E-709's naive EDF failed by deadline-ordering ALL cities (wrecked core phasing); here urgency+penalty apply
ONLY to the low-degree periphery, the core stays on nearest-arrival.

Instrumented (positive control <2min); checkpoints best path every 25 depths; resumable-by-restart.
Usage: python ch2_giant_deadline_beam.py [W=80] [K=18] [THRESH=40] [LAMBDA=10] [URG=40] [start=-1]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
CKPT = f"{ROOT}/cache/ch2_giant_deadline_beam_best.json"
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
OUT = defaultdict(list)                                         # i -> [(j,row)] cheap out-edges
for r, (i, j) in enumerate(KEYS):
    OUT[int(i)].append((int(j), r))
GMIN = np.where(FIN.any(1), np.nanmin(np.where(FIN, VALS, np.inf), 1), np.inf)
for i in OUT:
    OUT[i].sort(key=lambda jr: GMIN[jr[1]])

# --- periphery + deadlines (computed once) ---
INc = defaultdict(set)                                          # j -> set of source cities (cheap in-edges)
LASTDEP = defaultdict(float)                                    # j -> latest open departure epoch (deadline)
for r, (i, j) in enumerate(KEYS):
    fr = np.where(FIN[r])[0]
    if fr.size:
        INc[int(j)].add(int(i))
        LASTDEP[int(j)] = max(LASTDEP[int(j)], float(EPOCHS[fr[-1]]))
INDEG = {c: len(INc[c]) for c in cities}


def fine_cheap_arrival(i, j, row, t, dv_cap):
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= dv_cap:
                return dep, float(tof), dep + float(tof)
    return None


def build_periphery(thresh):
    P = set(c for c in cities if INDEG[c] < thresh)
    POUT = defaultdict(list)                                    # i -> [(j,row)] where j in P
    for r, (i, j) in enumerate(KEYS):
        if int(j) in P:
            POUT[int(i)].append((int(j), r))
    for i in POUT:
        POUT[i].sort(key=lambda jr: GMIN[jr[1]])
    return P, POUT


def candidates(i, t, visited, K, exc_left, POUT, P, urg):
    """Cheap candidates first (earliest-arrival), exceptions only when near-stuck, PLUS urgency candidates:
    periphery cities whose deadline is within `urg` days of now and that this city can still reach."""
    out = []
    for (j, row) in OUT[i]:
        if j in visited:
            continue
        res = fine_cheap_arrival(i, j, row, t, kt.dv_thr)
        if res is not None:
            out.append((j, res[2], res[1], 0))
            if len(out) >= K * 3:
                break
    out.sort(key=lambda c: c[1])
    out = out[:K]
    have = {c[0] for c in out}
    # urgency: force-offer near-deadline periphery cities even if not earliest
    for (j, row) in POUT.get(i, []):
        if j in visited or j in have:
            continue
        if LASTDEP[j] - t > urg:                               # deadline not yet imminent -> skip
            continue
        res = fine_cheap_arrival(i, j, row, t, kt.dv_thr)
        if res is None and exc_left > 0:
            res = fine_cheap_arrival(i, j, row, t, kt.dv_exc)
            if res is not None:
                out.append((j, res[2], res[1], 1)); have.add(j); continue
        if res is not None:
            out.append((j, res[2], res[1], 0)); have.add(j)
    # fallback exceptions if the frontier is nearly stuck
    if len([c for c in out if c[3] == 0]) < 4 and exc_left > 0:
        for (j, row) in OUT[i][:40]:
            if j in visited or j in have:
                continue
            res = fine_cheap_arrival(i, j, row, t, kt.dv_exc)
            if res is not None:
                out.append((j, res[2], res[1], 1)); have.add(j)
                if sum(c[3] for c in out) >= 4:
                    break
    return out


def strand_risk(vis, t, P):
    """# periphery cities not yet visited whose last departure window has already closed (unreachable)."""
    return sum(1 for j in P if j not in vis and LASTDEP[j] < t)


def main(W=80, K=18, thresh=40, LAMBDA=10.0, urg=40.0, start=-1):
    P, POUT = build_periphery(thresh)
    starts = [cities[start]] if start >= 0 else cities[:8]
    print(f"[E-719] deadline beam W={W} K={K} thresh={thresh} (|P|={len(P)}) LAMBDA={LAMBDA} urg={urg}d; "
          f"giant n={NG}; {len(starts)} seed(s)", flush=True)
    beam = [{"t": 0.0, "last": s, "vis": {s}, "path": [s], "exc": 0} for s in starts]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t": 0.0, "strands": len(P)}
    t0 = time.time(); pc_done = False
    for depth in range(1, NG):
        succ = []
        for st in beam:
            cs = candidates(st["last"], st["t"], st["vis"], K, kt.n_exc - st["exc"], POUT, P, urg)
            for (j, arr, tof, is_exc) in cs:
                succ.append({"t": arr, "last": j, "vis": st["vis"] | {j},
                             "path": st["path"] + [j], "exc": st["exc"] + is_exc})
        if not pc_done:
            nper = sum(1 for s in succ if s["last"] in P)
            print(f"[E-719] positive control: depth1 -> {len(succ)} successors ({nper} into periphery) "
                  f"[{time.time()-t0:.0f}s]", flush=True)
            pc_done = True
        if not succ:
            print(f"[E-719] beam stranded at depth {depth} (no successor)", flush=True)
            break
        # rank by makespan PLUS a penalty for periphery already stranded (the deadline-awareness)
        for s in succ:
            s["key"] = s["t"] + LAMBDA * strand_risk(s["vis"], s["t"], P)
        succ.sort(key=lambda s: s["key"])
        seen = set(); pruned = []                              # diversity: best-key per distinct last-city
        for s in succ:
            if s["last"] in seen:
                continue
            seen.add(s["last"]); pruned.append(s)
            if len(pruned) >= W:
                break
        beam = pruned if len(pruned) >= W // 2 else succ[:W]
        deepest = max(beam, key=lambda s: len(s["path"]))
        if len(deepest["path"]) > best["depth"]:
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]), "t": deepest["t"],
                    "strands": strand_risk(deepest["vis"], deepest["t"], P)}
        if depth % 20 == 0 or depth < 5:
            bt = min(beam, key=lambda s: s["t"])
            pv = sum(1 for c in bt["path"] if c in P)
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} min_t={bt['t']:.1f}d "
                  f"(d/leg {bt['t']/max(len(bt['path'])-1,1):.3f}) periph_in_path={pv}/{len(P)} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
        if depth % 25 == 0:
            json.dump(best, open(CKPT, "w"))
    pv = sum(1 for c in best["path"] if c in P)
    print(f"\n[E-719] DONE: deepest {best['depth']}/{NG}, makespan {best['t']:.1f}d "
          f"(d/leg {best['t']/max(best['depth']-1,1):.3f}); periphery threaded {pv}/{len(P)}; "
          f"rank-1=424.62 (E-710 baseline 558@283d) [{time.time()-t0:.0f}s]", flush=True)
    json.dump(best, open(CKPT, "w"))
    if best["depth"] >= NG - 2 and best["t"] < 424.62:
        print(f"[E-719] *** THREADS {best['depth']}/601 @ {best['t']:.0f}d < 424.62 -> RANK-1 territory. "
              f"Next: stitch 3x150 satellites + faithful udp verify + guard-bank + ESCALATE.", flush=True)
    elif best["depth"] > 558:
        print(f"[E-719] {best['depth']}/601 (> E-710's 558) -> deadline-awareness threads more periphery; "
              f"tune LAMBDA/urg/thresh toward 601.", flush=True)
    else:
        print(f"[E-719] {best['depth']}/601 (<= 558) -> periphery interleaving did not beat plain beam here; "
              f"sweep LAMBDA/thresh or the periphery needs backward/meet-in-middle placement.", flush=True)


if __name__ == "__main__":
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 18
    th = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    lam = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
    ur = float(sys.argv[5]) if len(sys.argv) > 5 else 40.0
    st = int(sys.argv[6]) if len(sys.argv) > 6 else -1
    main(W, K, th, lam, ur, st)
